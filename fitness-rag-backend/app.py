from fastapi import FastAPI
from pydantic import BaseModel
import chromadb
from google import genai
import os
from dotenv import load_dotenv
import psycopg2
from sentence_transformers import SentenceTransformer
from fastapi.middleware.cors import CORSMiddleware
import requests
import random
import base64
import re
from urllib.parse import quote

# ==========================
# LOAD ENV (GEMINI)
# ==========================
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

print("KEY LOADED:", api_key[:10] if api_key else "missing")

client_llm = genai.Client(api_key=api_key)

# ==========================
# FASTAPI
# ==========================
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# EMBEDDING MODEL
# ==========================
model = SentenceTransformer("all-MiniLM-L6-v2")

# ==========================
# CHROMA VECTOR DB
# ==========================
client = chromadb.Client()
collection = client.get_or_create_collection(name="fitness")


YOUTUBE_KEY = os.getenv("YOUTUBE_API_KEY")
EXERCISE_RECOMMENDATION_LIMIT = 8
VECTOR_SEARCH_RESULTS = 24
DISTANCE_THRESHOLD = 2.0
YOUTUBE_FALLBACK = "https://www.youtube.com/embed/_l3ySVKYVJ8"
IMAGE_FALLBACK_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn8n2UAAAAASUVORK5CYII="
)

IMAGE_CACHE = {}
YOUTUBE_CACHE = {}

# Common aliases for labels that often fail in exact YouTube search.
YOUTUBE_LABEL_ALIASES = {
    "step-ups": ["step up", "step ups", "step-up exercise"],
    "push-ups": ["push up", "push ups", "push-up exercise"],
    "pull-ups": ["pull up", "pull ups", "pull-up exercise"],
}


def _normalize_exercise_name(ex_name: str) -> str:
    return " ".join(str(ex_name).strip().lower().split())


def _extract_exercise_label(raw_text: str) -> str:
    """
    Extract the clean exercise name from a RAG sentence like:
      "Push-up is a bodyweight exercise..."         -> "Push-up"
      "Squat is a compound lower body exercise..."  -> "Squat"
      "Bicep curl isolates the biceps..."           -> "Bicep curl"
      "Bulgarian split squat strengthens legs..."   -> "Bulgarian split squat"

    Strategy: the exercise name is everything BEFORE the first verb/connector.
    """
    raw = (raw_text or "").strip()
    # Split on the first occurrence of common verb patterns
    # Use a regex that matches " is ", " are ", " improve", " target", " strengthen",
    # " isolate", " combine", " use", " perform", ":" — all typical in this corpus
    verb_pattern = re.compile(
        r'\s+(is|are|improve[sd]?|target[sd]?|strengthen[sd]?|isolate[sd]?|'
        r'combine[sd]?|uses?|performs?|build[sd]?|develop[sd]?|work[sd]?)\b',
        re.IGNORECASE
    )
    m = verb_pattern.search(raw)
    if m:
        label = raw[:m.start()].strip()
        # Sanity-check: label should be short and not contain a full sentence
        if 1 < len(label) < 60:
            return label

    # Fallback: first word group before colon
    if ":" in raw:
        candidate = raw.split(":")[0].strip()
        if 1 < len(candidate) < 60:
            return candidate

    # Last fallback: first 4 words
    words = raw.split()
    return " ".join(words[:4]) if words else raw[:40]


def _youtube_embed_search_url(label: str) -> str:
    query = quote((label or "fitness exercise").strip())
    # Use a reliable web search URL as fallback; frontend can open this directly.
    return f"https://www.youtube.com/results?search_query={query}"


def _youtube_query_candidates(label: str):
    """Build progressively broader query candidates for a label."""
    base = (label or "").strip()
    if not base:
        return []

    normalized = re.sub(r"\s+", " ", base).strip()
    dashed_to_space = normalized.replace("-", " ")
    no_punct = re.sub(r"[^a-zA-Z0-9 ]", "", dashed_to_space).strip()

    candidates = [normalized, dashed_to_space, no_punct]

    # Add configured aliases for known problematic names.
    alias_key = normalized.lower()
    candidates.extend(YOUTUBE_LABEL_ALIASES.get(alias_key, []))

    # Deduplicate while preserving order.
    seen = set()
    unique = []
    for c in candidates:
        c = c.strip()
        if c and c.lower() not in seen:
            seen.add(c.lower())
            unique.append(c)
    return unique


def youtube_link_for(label: str) -> str:
    """
    Search YouTube for a tutorial video for the given clean exercise label.
    Falls back to an exercise-specific embed search URL when API key/search fails.
    """
    label = (label or "").strip()
    if not label:
        return YOUTUBE_FALLBACK

    cache_key = label.lower()
    if cache_key in YOUTUBE_CACHE:
        return YOUTUBE_CACHE[cache_key]

    if not YOUTUBE_KEY:
        result = _youtube_embed_search_url(label)
        YOUTUBE_CACHE[cache_key] = result
        return result

    url = "https://www.googleapis.com/youtube/v3/search"

    # Try several query variants before giving up.
    for candidate in _youtube_query_candidates(label):
        query = f"{candidate} exercise proper form tutorial"
        print(f"[YOUTUBE] searching: {query}")

        params = {
            "part": "snippet",
            "q": query,
            "key": YOUTUBE_KEY,
            "maxResults": 10,
            "type": "video",
            "videoEmbeddable": "true",
            "safeSearch": "moderate",
            "relevanceLanguage": "en",
        }

        try:
            res = requests.get(url, params=params, timeout=8).json()
        except Exception as e:
            print(f"[YOUTUBE] request failed: {e}")
            continue

        items = res.get("items", [])
        if not items:
            print(f"[YOUTUBE] no results for: {query}")
            continue

        # Rank by how many candidate words appear in title.
        candidate_words = set(re.sub(r"[^a-z0-9 ]", " ", candidate.lower()).split()) - {"the", "a", "an", "and", "to", "of", "for", "how", "exercise"}
        ranked = []
        for item in items:
            title = item.get("snippet", {}).get("title", "").lower()
            score = sum(1 for w in candidate_words if w in title)
            ranked.append((score, item))

        ranked.sort(key=lambda x: x[0], reverse=True)
        best_item = ranked[0][1]
        video_id = best_item.get("id", {}).get("videoId")

        if video_id:
            result = f"https://www.youtube.com/embed/{video_id}"
            print(f"[YOUTUBE] -> selected video_id={video_id}")
            YOUTUBE_CACHE[cache_key] = result
            return result

    # Final fallback remains exercise-specific.
    result = _youtube_embed_search_url(label)
    YOUTUBE_CACHE[cache_key] = result
    return result


def generate_exercise_image(ex_name: str) -> str:
    key = _normalize_exercise_name(ex_name)
    if key in IMAGE_CACHE:
        return IMAGE_CACHE[key]

    prompt = (
        f"Minimalist fitness instruction illustration of the exercise {ex_name}. "
        "Stick figure, black lines, white background, fitness manual style."
    )

    try:
        response = client_llm.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
        )

        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                img_bytes = part.inline_data.data
                base64_img = base64.b64encode(img_bytes).decode()
                image_data = f"data:image/png;base64,{base64_img}"
                IMAGE_CACHE[key] = image_data
                return image_data
    except Exception:
        pass

    IMAGE_CACHE[key] = IMAGE_FALLBACK_DATA_URL
    return IMAGE_FALLBACK_DATA_URL

# ==========================
# LOAD DATA FROM POSTGRES → CHROMA
# ==========================
def load_data_to_chroma():
    conn = psycopg2.connect(
        dbname="fitness_rag",
        user="postgres",
        password="...123Finki",
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor()

    cursor.execute("SELECT id, content FROM documents;")
    rows = cursor.fetchall()

    texts = [r[1] for r in rows]
    ids = [str(r[0]) for r in rows]

    if not texts:
        return

    embeddings = model.encode(texts).tolist()

    existing_ids = set()
    try:
        existing_ids = set(collection.get()["ids"])
    except:
        pass

    new_texts, new_ids, new_embeddings = [], [], []

    for t, i, e in zip(texts, ids, embeddings):
        if i not in existing_ids:
            new_texts.append(t)
            new_ids.append(i)
            new_embeddings.append(e)

    if new_texts:
        collection.add(
            documents=new_texts,
            embeddings=new_embeddings,
            ids=new_ids
        )

    cursor.close()
    conn.close()

# load once on startup
load_data_to_chroma()

# ==========================
# REQUEST MODEL
# ==========================
class Query(BaseModel):
    question: str

# ==========================
# LANGUAGE DETECTION
# ==========================
def is_mk(text: str) -> bool:
    mk_chars = "ѓжчќшљњџабвгдезијклмнопрстуфхцчџш"
    return any(ch in text.lower() for ch in mk_chars)


def is_plan_request(text: str) -> bool:
    t = text.lower()
    keywords = ["plan", "workout plan", "7-day", "седум", "план", "неделен план"]
    return any(k in t for k in keywords)

# ==========================
# SAFE GEMINI TEXT
# ==========================
def extract_text(resp):
    try:
        if hasattr(resp, "text") and resp.text:
            return resp.text

        if hasattr(resp, "candidates") and resp.candidates:
            cand = resp.candidates[0]
            if hasattr(cand, "content") and cand.content.parts:
                return cand.content.parts[0].text
    except Exception as e:
        print("EXTRACT ERROR:", e)

    return None



# ==========================
# GENERIC FALLBACK
# ==========================
def general_fallback(question):
    if is_mk(question):
        return """
КРАТОК ОДГОВОР:
За добро здравје вежбај редовно и јади балансирана исхрана.

ДЕТАЛЕН ОДГОВОР:
Комбинирај кардио (трчање, јаже, брзо одење) и силов тренинг 3-4 пати неделно.
Спиј доволно и внесувај протеини и вода.
"""
    else:
        return """
SHORT ANSWER:
Exercise regularly and maintain a balanced diet.

DETAILED ANSWER:
Combine cardio (running, jump rope, walking) with strength training 3-4 times per week.
Sleep well, stay hydrated and eat enough protein.
"""

# ==========================
# ROOT
# ==========================
@app.get("/")
def home():
    return {"message": "Fitness RAG API is running!"}

@app.get("/ping")
def ping():
    return {"ok": True}

# ==========================
# EXERCISE NAME EXTRACTION
# ==========================
def extract_exercise_name(text: str) -> str:
    t = text.lower()

    if "step" in t: return "step ups"
    if "push" in t: return "push ups"
    if "squat" in t: return "squats"
    if "plank" in t: return "plank"
    if "lunge" in t: return "lunges"
    if "burpee" in t: return "burpees"
    if "crunch" in t or "abs" in t: return "abs"
    if "deadlift" in t: return "deadlift"
    if "pull" in t: return "pull ups"
    if "bench" in t: return "bench press"

    return text


def dedupe_documents(documents):
    cleaned = []
    seen = set()

    for doc in documents:
        normalized = str(doc).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)

    return cleaned


def select_recommended_documents(documents, distances, limit=EXERCISE_RECOMMENDATION_LIMIT):
    relevant_docs = []
    fallback_docs = []
    seen = set()

    for doc, dist in zip(documents, distances):
        normalized = str(doc).strip()
        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        if dist < DISTANCE_THRESHOLD and len(relevant_docs) < limit:
            relevant_docs.append(normalized)
        fallback_docs.append(normalized)

    if len(relevant_docs) >= limit:
        return relevant_docs[:limit]

    for doc in fallback_docs:
        if doc not in relevant_docs:
            relevant_docs.append(doc)
        if len(relevant_docs) >= limit:
            break

    return relevant_docs[:limit]

# MAIN ENDPOINT
# ==========================
@app.post("/ask")
def ask(q: Query):
    try:
        # 1️⃣ embed question
        query_embedding = model.encode([q.question]).tolist()

        # 2️⃣ vector search with scores
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=VECTOR_SEARCH_RESULTS,
            include=["documents", "distances"]
        )

        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        # 3️⃣ filter relevant docs and keep up to 8 unique recommendations
        docs = select_recommended_documents(docs, distances)
        # 4️⃣ decide if we use context
        use_context = len(docs) > 0

        if use_context:
            context = " ".join(docs)
            context_block = f"Context:\n{context}"
        else:
            context_block = "No specific exercise context available."

        if is_plan_request(q.question):

            conn = psycopg2.connect(
                dbname="fitness_rag",
                user="postgres",
                password="...123Finki",
                host="localhost",
                port="5432"
            )
            cursor = conn.cursor()

            cursor.execute("SELECT content FROM documents")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            all_exercises = list(set([r[0] for r in rows]))

            if len(all_exercises) < 16:
                return {"answer": "Not enough exercises in database."}

            selected = random.sample(all_exercises, 16)

            allowed_exercises = "\n".join(selected)

            lang = "Macedonian" if is_mk(q.question) else "English"

            plan_prompt = f"""
        You are a certified personal trainer.

        You MUST build a 7-day workout plan using ONLY the exercises listed below.

        ALLOWED EXERCISES:
        {allowed_exercises}

        User request:
        {q.question}

        Rules:
        - Use ONLY exercises from the allowed list
        - Do not repeat the same exercise on multiple days
        - Create Day 1 to Day 7
        - Include sets and reps
        - Include rest days
        - Answer ONLY in {lang}
        """

            resp = client_llm.models.generate_content(
                model="gemini-2.0-flash",
                contents=[{
                    "role": "user",
                    "parts": [{"text": plan_prompt}]
                }]
            )

            answer = extract_text(resp)

            return {
                "question": q.question,
                "type": "hybrid_database_plan",
                "answer": answer
            }

        # 5️⃣ prompt
        lang = "Macedonian" if is_mk(q.question) else "English"
        prompt = f"""
You are a certified professional fitness coach.

{context_block}

Question:
{q.question}

Instructions:
- Answer ONLY in {lang}
- Do NOT use any other language
- If context exists, use it
- If not, use general fitness knowledge
- Provide:
  1) SHORT answer (2-3 sentences)
  2) DETAILED answer with advice
"""

        # 6️⃣ Gemini
        try:
            resp = client_llm.models.generate_content(
                model="gemini-2.0-flash",
                contents=[{
                    "role": "user",
                    "parts": [{"text": prompt}]
                }]
            )

            answer = extract_text(resp)

            if not answer:
                answer = general_fallback(q.question)

        except:
            answer = general_fallback(q.question)

        structured_exercises = []

        for d in docs:
            # Extract clean label (e.g. "Bicep curl") for image + YouTube search
            label = _extract_exercise_label(d)
            print(f"[DEBUG] raw='{d[:60]}' -> label='{label}'")

            structured_exercises.append({
                "name": d,          # FULL sentence shown on card
                "label": label,     # clean name for image/video lookups
                "video": youtube_link_for(label),   # pass label directly, not raw
                "images": [generate_exercise_image(label)],
                "raw": d,
            })

        return {
            "question": q.question,
            "answer": answer,
            "exercises": structured_exercises
        }

    except Exception as e:
        return {"error": str(e)}

@app.get("/exercise-assets")
def exercise_assets(text: str):
    """Return best-effort label/image/video for a saved exercise entry."""
    label = _extract_exercise_label(text)
    return {
        "label": label,
        "image": generate_exercise_image(label),
        "video": youtube_link_for(label),
    }


from fastapi.responses import FileResponse

@app.get("/download/{filename}")
def download_file(filename: str):
    path = f"plans/{filename}"
    media_type = "application/pdf" if filename.lower().endswith(".pdf") else "text/plain"
    return FileResponse(path, media_type=media_type, filename=filename)

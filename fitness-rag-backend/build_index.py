import os
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import chromadb

load_dotenv()

print("Loading model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

conn = psycopg2.connect(
    dbname="fitness_rag",
    user="postgres",
    password=os.getenv("DB_PASSWORD"),
    host="localhost",
    port="5432"
)
cursor = conn.cursor()

cursor.execute("SELECT id, content FROM documents;")
rows = cursor.fetchall()

texts = [row[1] for row in rows]
ids = [str(row[0]) for row in rows]

print("Creating embeddings...")
embeddings = model.encode(texts).tolist()

# Explicit distance space (see app.py for the full rationale): Chroma
# silently defaults to l2 with no metadata — make it explicit so
# DISTANCE_THRESHOLD stays meaningful.
client = chromadb.Client()
collection = client.get_or_create_collection(name="fitness", metadata={"hnsw:space": "l2"})

collection.add(
    documents=texts,
    embeddings=embeddings,
    ids=ids
)

print("✅ VECTOR DB READY")

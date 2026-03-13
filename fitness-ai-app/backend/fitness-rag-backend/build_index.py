import psycopg2
from sentence_transformers import SentenceTransformer
import chromadb

print("Loading model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

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

texts = [row[1] for row in rows]
ids = [str(row[0]) for row in rows]

print("Creating embeddings...")
embeddings = model.encode(texts).tolist()

client = chromadb.Client()
collection = client.get_or_create_collection(name="fitness")

collection.add(
    documents=texts,
    embeddings=embeddings,
    ids=ids
)

print("✅ VECTOR DB READY")

import psycopg2

# connect to postgres
conn = psycopg2.connect(
    dbname="fitness_rag",
    user="postgres",
    password="...123Finki",
    host="localhost",
    port="5432"
)

cursor = conn.cursor()

# read file
with open("data/hku_academic.txt", "r", encoding="utf-8") as f:
    text = f.read()

# split into paragraphs
chunks = text.split("\n\n")

print(f"Chunks found: {len(chunks)}")

# insert into database
for chunk in chunks:
    clean = chunk.strip()
    if len(clean) > 50:
        cursor.execute(
            "INSERT INTO documents (content) VALUES (%s)",
            (clean,)
        )

# ===== EXERCISES DATASET =====

with open("data/exercises.txt", "r", encoding="utf-8") as f:
    text2 = f.read()

chunks2 = text2.split("\n\n")

for chunk in chunks2:
    clean = chunk.strip()
    if len(clean) > 30:
        cursor.execute(
            "INSERT INTO documents (content) VALUES (%s)",
            (clean,)
        )

conn.commit()
cursor.close()
conn.close()

print("DATA SUCCESSFULLY INSERTED 🚀")

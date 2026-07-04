import chromadb
import json

chroma_client = chromadb.Client()
collection= chroma_client.create_collection(name="airline_policies")

policies = [
    "IndiGo Policy: 1 free cabin bag (up to 7kg) and 1 free checked bag (up to 15kg) are included. Extra checked baggage costs ₹550 per kg. Pets are NOT allowed in the cabin.",
    "Air India Policy: 1 free cabin bag (up to 8kg) and 1 free checked bag (up to 15kg) are included. Extra baggage is ₹600 per kg. Small pets ARE allowed in the cabin for a ₹4000 fee.",
    "SpiceJet Policy: 1 free cabin bag (up to 7kg) and 1 free checked bag (up to 15kg) are included. Extra baggage is ₹550 per kg. Pets are NOT allowed in the cabin.",
    "Akasa Air Policy: 1 free cabin bag (up to 7kg) and 1 free checked bag (up to 15kg) are included. Extra baggage is ₹500 per kg. Pets ARE allowed in the cabin (Akasa Pets) for a ₹3000 fee.",
    "Air India Express Policy: 1 free cabin bag (up to 7kg) included. 'Xpress Lite' fares do NOT include free checked bags. Pre-booked extra baggage is ₹500 per kg. Pets are NOT allowed."
]

collection.add(
    documents=policies,
    ids=[f"policy_{i}" for i in range(len(policies))],
    metadatas=[{"source": f"airline_{i}"} for i in range(len(policies))]
)

print('brains loaded')

def search_airline_policy(query):
    results = collection.query(
        query_texts=[query],
        n_results=1
    )
    retrived_policy = results.get('documents',[[]])[0]
    return json.dumps({"retrieved_policies": retrived_policy})
"""Quick script to check if Qdrant has data"""
from denmark_academy.retrieval.qdrant import QdrantRepository

def main():
    repo = QdrantRepository()
    
    collections = [
        "da_learning_chunks",
        "da_official_questions",
        "da_official_answers",
        "da_explanations"
    ]
    
    print("Checking Qdrant collections...\n")
    
    for collection in collections:
        try:
            if repo.client.collection_exists(collection):
                info = repo.client.get_collection(collection)
                count = info.points_count if hasattr(info, 'points_count') else 0
                print(f"✅ {collection}: {count} points")
            else:
                print(f"❌ {collection}: Does not exist")
        except Exception as e:
            print(f"❌ {collection}: Error - {e}")
    
    print("\n" + "="*50)
    print("Summary:")
    print("="*50)
    
    # Check learning material
    try:
        if repo.client.collection_exists("da_learning_chunks"):
            info = repo.client.get_collection("da_learning_chunks")
            count = info.points_count if hasattr(info, 'points_count') else 0
            if count > 0:
                print(f"✅ Learning material: {count} chunks available")
                print("   → Smart Practice will use RAG context")
            else:
                print("⚠️ Learning material: Collection empty")
                print("   → Smart Practice will use AI general knowledge")
        else:
            print("⚠️ Learning material: Not ingested yet")
            print("   → Smart Practice will use AI general knowledge")
    except Exception as e:
        print(f"❌ Error checking learning material: {e}")
    
    # Check questions
    try:
        if repo.client.collection_exists("da_official_questions"):
            info = repo.client.get_collection("da_official_questions")
            count = info.points_count if hasattr(info, 'points_count') else 0
            if count > 0:
                print(f"✅ Official questions: {count} questions available")
                print("   → Smart Practice will match question style")
            else:
                print("⚠️ Official questions: Collection empty")
                print("   → Smart Practice will create generic style")
        else:
            print("⚠️ Official questions: Not ingested yet")
            print("   → Smart Practice will create generic style")
    except Exception as e:
        print(f"❌ Error checking questions: {e}")
    
    print("\n" + "="*50)
    print("To ingest data, run:")
    print("="*50)
    print("python -m apps.worker_ingestion.main . --migrate")
    print("="*50)

if __name__ == "__main__":
    main()

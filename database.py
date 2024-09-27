from pymongo import MongoClient, errors

def connect_to_mongodb(uri, db_name):
    """
    Connects to MongoDB and returns the database object.

    Parameters:
    - uri (str): MongoDB connection URI.
    - db_name (str): Name of the database.

    Returns:
    - db: Database object if connection is successful, else None.
    """
    try:
        client = MongoClient(uri)
        db = client[db_name]
        print("Connected to MongoDB")
        return db
    except errors.PyMongoError as e:
        print(f"Error: Could not connect to MongoDB.\n{e}")
        return None

def insert_document(db, collection_name, document):
    """
    Inserts a document into the specified collection.

    Parameters:
    - db: Database object.
    - collection_name (str): Name of the collection.
    - document (dict): The document to insert.
    """
    try:
        collection = db[collection_name]
        result = collection.insert_one(document)
        print(f"Inserted document with ID: {result.inserted_id}")
    except errors.PyMongoError as e:
        print(f"Error: Could not insert document.\n{e}")

def find_documents(db, collection_name, query=None):
    """
    Finds documents in the specified collection based on the query.

    Parameters:
    - db: Database object.
    - collection_name (str): Name of the collection.
    - query (dict, optional): Query to filter documents. If None, all documents are retrieved.

    Returns:
    - list: A list of documents.
    """
    try:
        collection = db[collection_name]
        cursor = collection.find(query) if query else collection.find()
        return list(cursor)
    except errors.PyMongoError as e:
        print(f"Error: Could not retrieve documents.\n{e}")
        return []

def check_db(db, collection_name, name):
    """
    Checks if a document with a specific name exists in the collection.

    Parameters:
    - db: Database object.
    - collection_name (str): Name of the collection.
    - name (str): The name to check for in the documents.

    Returns:
    - bool: True if the document exists, otherwise False.
    """
    documents = find_documents(db, collection_name)
    names = [doc.get("NAME") for doc in documents]
    return name in names 

def get_info(db, collection_name, name):
    """
    Retrieves the document with a specific name from the collection.

    Parameters:
    - db: Database object.
    - collection_name (str): Name of the collection.
    - name (str): The name to retrieve.

    Returns:
    - dict: The document with the specific name, or None if not found.
    """
    documents = find_documents(db, collection_name, {"NAME": name})
    return documents[0] if documents else None

def get_raw_url(db, collection_name):
    """
    Retrieves all URLs from documents in the collection.

    Parameters:
    - db: Database object.
    - collection_name (str): Name of the collection.

    Returns:
    - list: A list of URLs.
    """
    documents = find_documents(db, collection_name)
    return [doc.get("URL") for doc in documents]

def update_document(db, collection_name, query, new_values):
    """
    Updates documents in the specified collection based on the query and new values.

    Parameters:
    - db: Database object.
    - collection_name (str): Name of the collection.
    - query (dict): Query to filter documents to update.
    - new_values (dict): The new values to set in the document(s).

    Returns:
    - str: A message indicating the result of the update operation.
    """
    try:
        collection = db[collection_name]
        result = collection.update_one(query, new_values)

        if result.matched_count > 0:
            return "Document updated successfully."
        else:
            return "No document matched the query."

    except errors.PyMongoError as e:
        return f"Error: Could not update document.\n{e}"

# Example usage
if __name__ == "__main__":
    uri = "mongodb://localhost:27017/"
    db_name = "mydatabase"
    collection_name = "mycollection"

    # Connect to MongoDB
    db = connect_to_mongodb(uri, db_name)
    if not db:
        exit()

    # Insert a document
    document = {"NAME": "John Doe", "URL": "http://example.com"}
    insert_document(db, collection_name, document)

    # Check if a document exists
    name = "John Doe"
    exists = check_db(db, collection_name, name)
    print(f"Document exists: {exists}")

    # Retrieve information
    info = get_info(db, collection_name, name)
    print(f"Document info: {info}")

    # Retrieve URLs
    urls = get_raw_url(db, collection_name)
    print(f"URLs: {urls}")

    # Update a document
    query = {"NAME": name}
    new_values = {"$set": {"URL": "http://newexample.com"}}
    update_message = update_document(db, collection_name, query, new_values)
    print(update_message)

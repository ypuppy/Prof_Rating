from db import db

print("Connected DB name:", db.name)
print("Collections:", db.list_collection_names())

from db import professors_col

for prof in professors_col.find():
    print(prof)

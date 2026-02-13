import pathlib

def main():
    dbs = [str(p) for p in pathlib.Path(".").rglob("*.db")]
    print(dbs)

if __name__ == "__main__":
    main()

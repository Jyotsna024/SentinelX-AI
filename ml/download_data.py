import urllib.request
import pathlib
import sys

DATA_DIR = pathlib.Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_URL = "https://raw.githubusercontent.com/Nir-J/ML-Projects/master/UNSW-Network_Packet_Classification/UNSW_NB15_training-set.csv"
TEST_URL = "https://raw.githubusercontent.com/Nir-J/ML-Projects/master/UNSW-Network_Packet_Classification/UNSW_NB15_testing-set.csv"

def download_file(url, dest):
    print(f"Downloading {url} ...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            with open(dest, "wb") as f:
                f.write(response.read())
        print(f"Saved to {dest}")
    except Exception as e:
        print(f"Error downloading {url}: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    download_file(TRAIN_URL, DATA_DIR / "UNSW_NB15_training-set.csv")
    download_file(TEST_URL, DATA_DIR / "UNSW_NB15_testing-set.csv")
    print("Download completed successfully!")

if __name__ == "__main__":
    main()

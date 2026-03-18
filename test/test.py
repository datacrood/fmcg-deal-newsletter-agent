from turtle import down
import trafilatura

def trafil(url):
    downloaded = trafilatura.fetch_url(url)
    # print(downloaded)
    if downloaded:
        res = trafilatura.extract(downloaded, include_comments=False)
        print(res)
        


if __name__ == "__main__":
    url = "https://substack.com/@loulundberg/p-189004431"
    trafil(url)
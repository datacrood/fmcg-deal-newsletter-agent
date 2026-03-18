## Ingestion Layer
- I searched on Google: What does FMCG deals: M&A fetches and shows results to understand the data first. Searched from already existing newsletters to understand the formatting and details. 
  - I run a chat with ChatGPT and asked some preliminary questions to understand the problem statement depth and assumtions: 
    - How occasional the news of FMCG M&A occurs? Monthly (Not weekly): supported by my observation of existing newsletter frequency - biweekly or monthly. 
    Conclusion: Safe assumption: The word "recent" given in the problem statement means biweekly or monthly.
    - What would be the best source to fetch relevant news? NewsAPI.org, Google News RSS
  - This was necessary to setup a chron job that will fetch all the news between current week and lastly run cron job week and store in json format.
- For now, assuming input-data.json for simplicity containing all the articles relevant to FMCG recent deals.
- If I have to make the data fetcher, I would run cron nightly, to fetch the latest news from fixed rss urls with focus on FMCG recent deal activities (Mergers & Acquisition). With time I would increase the source of input with reliable and credible sources. As better input data will lead to better output results
- Others: Installed pytest for quick article fetch testing.
- Idea: Improve query to fetch good articles from scratch: using prompt engineering: Create a list of basic vocubulary to search for like FMCG industry names (ever-growing) and high quality deal terminologies or negative sampling by introducing feedback loop


- Issues: from first data capture -> Bloated article, HTML is not cleaned: leading to misformatting, NewsAPI is pulling lot of noise using keyword: FMCG AND (acquisition OR merger OR investment);
- (FMCG OR "consumer goods" OR CPG) AND (acquisition OR merger OR takeover OR "stake sale" OR buyout); MAX_CONTENT_LEN = 15,000 chars per article: Removed the articles fully intead of storing them in half;  Added _strip_html() used on RSS summaries, titles, and NewsAPI content fallback; _clean() to strip whitespaces
- Currently added specific keywords to keep relevancy of articles high. In real world, we might skip some news, but not provide un related news it will lead to lose in readers trust. Will remove it once scoring and filtering is set.

## Filtering layer
- There might be articles that will be irrelevant to deals: we can apply logic based basic filtering instead of investing LLM here to large article sources (Optimisnig for LLM cost) with the trade off of missing some good articles sometimes which is acceptable to an extent for a newsletter use case. 
- Since we are collecting data from different sources (NewsAPI and Google RSS) we might have similar articles: We need to remove such duplicacy of articles. It might have less chances of url dedup if sources are fixed, Title can be similar so it's required, Further we can use TF_IDF (may use BM25 too) (Might miss different language articles so assumption to extract only englisth articles for now) for the content matching (Alternatively try setnence embedding model). We can also use spacy to extract root verb lemma that belongs to {acquire, merge, buy...} or ORGS{HUL, etc...}: 
  - Idea can further create scoring system from spacy to pre-filter threshold basis articles to gate LLM calls for reasoning based filtering for cost effectiveness.
  - Spacy entity-pair: (Acquirer, Target) by depdency parse: grouping articles by these pairs and applying fuzzy matching
- Content: We can use Spacy nlp.pipe() for the MONEY entity extraction replacing regex to catch formats like EUR, $, ₹ etc...


## Scoring:
- Now I have the headline and the content -> The content size is big for LLM ranking or extraction so we need to use the heading itself for maximum feature extraction that's possible such as credebility checking -- Doing web search and getting other headlines and sending this hybrid headline to find credebility, Talking about FMCG or not. Use Metadata too
- After de dup I can directly send the deduped selected article for final recommendation (since duplicated in multiple sources: Assume it would be true: Different urls (already duped with same content = safe to assume go forward))
- Fallback if LLM call fails = hardcoded simple logics; 
- Thought: Do I even need so big content? when I just want to tell the breif about the Articles


Problems: Generic articles without any industry merger but overall scene: Tried Scispacy (ORG, MONEY...) but not doing as good job as LLM: 

##FUture

## Solved problem
- The LLM call was sequential for all articles, made it parallel using asyncio and OpenAI async .ainvoke()
- LLM calls getting stuck: Added a timeout. 



## Learnings
- Content hashing is used for exact word to word easy duplicate handling. 
- The crossover point: MinHash+LSH beats brute force at roughly 10K+ documents. Below that, the index construction overhead       
  (building hash tables, banding, bucketing) costs more than just computing all pairwise similarities directly.
- Dedup needs factual identity. Embeddings encode semantic category. Use embeddings for relevance (is this about FMCG deals?). Use lexical methods for identity (is this the same deal?). At this document scale, TF-IDF cosine similarity is the right tool because deal articles are distinguished by named entities (companies, amounts, dates) which surface naturally as high-IDF terms. Embedding-based approaches risk conflating different deals in the same sector since they compress entity-level detail into semantic similarity
- I can directly call LLM on all input articles: and structure the format: 
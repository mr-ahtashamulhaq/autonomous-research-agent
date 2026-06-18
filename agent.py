import os
import logging
import argparse
from dotenv import load_dotenv  # reads key=value pairs from .env into os.environ

# Load .env file before anything else reads os.environ
load_dotenv()

from typing_extensions import TypedDict
from typing import List, Dict, Optional
from langchain_groq import ChatGroq
from tavily import TavilyClient
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser  # extracts just the .content string from the LLM message object
from langgraph.graph import StateGraph, START, END

# Configure structured logging - production apps log, they don't print
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("research_agent")

# llama-3.3-70b-versatile is Groq's fastest large model - good balance of
# speed and quality for research synthesis tasks.
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)

tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


class ResearchState(TypedDict):
    topic: str                      # user's original research question
    search_queries: List[str]       # the 5 queries the Plan node generates
    search_results: List[Dict]      # list of dicts, each: {title, url, snippet}
    full_text: str                  # all extracted article text joined together
    report: str                     # LLM's first-draft structured report
    final_report: str               # reviewed, cited, finalised report
    progress: Optional[List[str]]   # log of completed node names (for API streaming)


plan_chain = ChatPromptTemplate.from_template(
    """You are a senior research analyst. Your task is to decompose a research topic into
highly specific, effective web search queries that will surface authoritative sources.

Rules:
- Generate exactly 5 search queries
- Each query should target a different angle: recent news, academic/expert analysis,
  statistics/data, real-world applications, and challenges/criticism
- Make queries specific enough to avoid generic results (include years, domains, or
  qualifiers where helpful)
- Output ONLY the queries, one per line, no numbering, no bullets, no extra text

Research Topic: {topic}"""
) | llm | StrOutputParser()  # making a chain: take prompt → give it to LLM → take LLM output → give it to StrOutputParser()


def plan_node(state: ResearchState) -> dict:
    """Decompose the topic into 5 targeted search queries."""
    raw = plan_chain.invoke({"topic": state["topic"]})
    queries = [q.strip() for q in raw.split("\n") if q.strip()]  # clean list of query strings

    logger.info("Plan node complete | queries_generated=%d | topic=%r", len(queries), state["topic"])

    # LangGraph nodes must return a dictionary containing only the key they're
    # updating - not the entire state. LangGraph merges this back into the state.
    return {
        "search_queries": queries,
        "progress": (state.get("progress") or []) + ["plan"],
    }


def search_node(state: ResearchState) -> dict:
    """Run each query through Tavily and collect URLs + snippets."""
    results = []
    for q in state["search_queries"]:
        # max_results=5 gives us enough breadth per query while keeping API costs low
        for r in tavily.search(q, max_results=5)["results"]:
            results.append({
                "title":   r["title"],
                "url":     r["url"],
                "snippet": r.get("content", ""),  # short excerpt Tavily returns alongside the URL
            })  # building List[Dict] - each Dict is {title, url, snippet}

    logger.info("Search node complete | results=%d | queries=%d", len(results), len(state["search_queries"]))

    return {
        "search_results": results,
        "progress": (state.get("progress") or []) + ["search"],
    }


def read_node(state: ResearchState) -> dict:
    """Pull full article text from the most relevant URLs via Tavily Extract."""
    # Take only the top 8 unique URLs to stay within Tavily Extract rate limits
    urls = list(dict.fromkeys(r["url"] for r in state["search_results"]))[:8]

    # tavily.extract returns: [{"url": "...", "raw_content": "full page text"}, ...]
    extracted = tavily.extract(urls=urls)["results"]

    # Join all article texts into one big context block.
    # 3 000 chars per article keeps the context window manageable while giving
    # the LLM enough material to synthesise a quality report.
    full_text = "\n\n---\n\n".join(
        f"SOURCE: {r['url']}\n\n{r['raw_content'][:3000]}"
        for r in extracted
    )

    logger.info("Read node complete | articles_extracted=%d | urls_attempted=%d", len(extracted), len(urls))

    return {
        "full_text": full_text,
        "progress": (state.get("progress") or []) + ["read"],
    }


synthesise_chain = ChatPromptTemplate.from_template(
    """You are an expert research analyst and science communicator. Your job is to synthesise
raw source material into a clear, well-structured, insightful research report.

Instructions:
- Use ONLY the information present in the sources below - do not add outside knowledge
- Write 800–1200 words
- Structure your report with the following Markdown sections:
  ## Executive Summary
  (2–3 sentences capturing the most important finding)

  ## Key Findings
  (4–6 findings, each with a ### subheading and 2–3 paragraph explanation)

  ## Analysis & Implications
  (What do these findings mean? What trends or patterns emerge?)

  ## Conclusion
  (Synthesise the above into a forward-looking closing paragraph)

- When citing a source, use inline notation like [Source: domain.com]
- Write in a professional but accessible tone - clear to a non-expert reader
- Do NOT include a sources list at the end (the Review node will add that)

Research Topic: {topic}

--- SOURCE MATERIAL ---
{full_text}
"""
) | llm | StrOutputParser()


def synthesise_node(state: ResearchState) -> dict:
    """Generate the first-draft structured report from source material."""
    report = synthesise_chain.invoke({
        "topic":     state["topic"],
        "full_text": state["full_text"],
    })

    logger.info("Synthesise node complete | report_length=%d chars", len(report))

    return {
        "report": report,
        "progress": (state.get("progress") or []) + ["synthesise"],
    }


review_chain = ChatPromptTemplate.from_template(
    """You are a rigorous fact-checker and editor. Your job is to review a research report
against its original sources, correct any inaccuracies, and produce a polished final version.

Instructions:
1. Read the source material carefully
2. Check every claim in the report - remove or soften any claim not directly supported by sources
3. Where a claim IS supported, strengthen the inline citation: use [1], [2] etc. notation
4. Fix any awkward phrasing, improve flow, but do NOT change the structure or add new claims
5. At the very end, append a ## Sources section with a numbered list of URLs used,
   formatted as:
   [1] Title - https://url.com
   [2] Title - https://url.com
   ...
6. Also append a brief ## Research Confidence note (1–2 sentences) assessing how well
   the sources cover the topic

Return ONLY the final, polished report - do not include any meta-commentary or preamble.

--- SOURCE MATERIAL ---
{full_text}

--- DRAFT REPORT ---
{report}
"""
) | llm | StrOutputParser()


def review_node(state: ResearchState) -> dict:
    """Fact-check the draft, add numbered citations, finalise the report."""
    final = review_chain.invoke({
        "full_text": state["full_text"],
        "report":    state["report"],
    })  # returns a single str - the complete, polished final report

    logger.info("Review node complete | final_report_length=%d chars", len(final))

    return {
        "final_report": final,
        "progress": (state.get("progress") or []) + ["review"],
    }


# Creates a new graph, telling it the shape of state to expect (ResearchState)
graph = StateGraph(ResearchState)

# Add each node by name, pointing to its function
for name, fn in [
    ("plan",       plan_node),
    ("search",     search_node),
    ("read",       read_node),
    ("synthesise", synthesise_node),
    ("review",     review_node),
]:
    graph.add_node(name, fn)

# Wire the nodes in a straight sequence: START → plan → search → read → synthesise → review → END
graph.add_edge(START, "plan")
graph.add_edge("plan", "search")
graph.add_edge("search", "read")
graph.add_edge("read", "synthesise")
graph.add_edge("synthesise", "review")
graph.add_edge("review", END)

# compile() locks the graph and returns a runnable agent object
agent = graph.compile()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Autonomous Research Agent - powered by LangGraph + Groq + Tavily"
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="Impact of large language models on software engineering productivity",
        help="The research topic to investigate",
    )
    args = parser.parse_args()

    logger.info("Starting research agent | topic=%r", args.topic)
    result = agent.invoke({"topic": args.topic, "progress": []})
    logger.info("Research complete | report_length=%d chars", len(result["final_report"]))

    print("\n" + result["final_report"])

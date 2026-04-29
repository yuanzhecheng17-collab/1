
# Research & Patent Survey Agent

An AI-powered research and patent survey agent for scientific literature review, technology scouting, and patent landscape analysis.

## Overview

Research & Patent Survey Agent is an automated research assistant designed to help researchers, engineers, and R&D teams quickly understand a technical field. Given a research topic, the system automatically expands search queries, retrieves academic papers and patents from public data sources, ranks the results by relevance, and generates a structured survey report.

The project aims to reduce the time spent on repetitive manual searching, screening, and summarization during early-stage research, project planning, thesis topic selection, and patent analysis.

## Core Problem

In traditional research and patent investigation workflows, users usually need to manually search across multiple platforms, design different keyword combinations, screen large numbers of results, and summarize findings by hand.

This process has several pain points:

- Research papers and patents are distributed across different databases.
- Designing effective search queries is time-consuming and easy to get wrong.
- Screening large volumes of papers and patents requires repetitive manual work.
- Academic research and patent information are often analyzed separately.
- Technology trend analysis heavily depends on personal experience.
- Important papers, patents, or emerging research directions may be missed.

This project addresses these problems by automating the entire workflow from topic input to structured report generation.

## Key Features

- Automatic query expansion based on the input research topic
- Academic paper search using OpenAlex and Crossref
- Patent search using PatentsView
- Data cleaning and duplicate removal
- Relevance ranking based on topic matching, citations, and publication year
- Extraction of key papers and patents
- Automatic Markdown report generation
- CSV and JSON result export
- Optional LLM-enhanced query planning and report writing
- Modular multi-agent architecture

## Multi-Agent Architecture

The system is designed as a multi-agent workflow. Each agent is responsible for a specific stage of the research process.

### 1. Query Planner Agent

Generates multiple search queries from the original research topic.  
For example, given:

```text
GH4169 alloy additive manufacturing thermal simulation
````

The agent may generate queries related to:

```text
GH4169 alloy additive manufacturing review
GH4169 alloy additive manufacturing modeling simulation
GH4169 residual stress thermal history
Inconel 718 additive manufacturing
nickel-based superalloy microstructure evolution
```

### 2. Literature Search Agent

Retrieves academic papers from public scholarly databases such as:

* OpenAlex
* Crossref

The extracted paper metadata includes:

* Title
* Authors
* Publication year
* DOI
* Venue
* Abstract
* Citation count
* Source URL

### 3. Patent Search Agent

Retrieves patent information from public patent databases such as:

* PatentsView

The extracted patent metadata includes:

* Patent title
* Abstract
* Patent number
* Publication date
* Assignees
* Inventors
* Patent URL

### 4. Relevance Ranking Agent

Ranks papers and patents according to multiple factors, including:

* Keyword matching in titles and abstracts
* Topic relevance
* Citation count
* Publication year
* Patent publication date

This helps users focus on the most relevant and valuable results first.

### 5. Report Writer Agent

Generates a structured Markdown report containing:

* Search strategy
* Search queries
* Overall findings
* Key papers
* Key patents
* Main technical trends
* Potential research gaps
* Suggested next steps

### 6. Export Agent

Exports the final results into reusable files:

```text
survey_report.md
papers.csv
patents.csv
raw_result.json
```

## Workflow

```text
Input research topic
        ↓
Query Planner Agent
        ↓
Literature Search Agent
        ↓
Patent Search Agent
        ↓
Data Cleaning & Deduplication
        ↓
Relevance Ranking Agent
        ↓
Report Writer Agent
        ↓
Markdown / CSV / JSON Export
```

## Long-Chain Reasoning

This project is not just a keyword search tool. It follows a long-chain reasoning process:

```text
Topic understanding
 → Query expansion
 → Multi-source data retrieval
 → Data cleaning
 → Relevance evaluation
 → Paper-patent comparison
 → Trend summarization
 → Research gap identification
 → Report generation
```

For example, when analyzing a technical field, the system does not simply return a list of papers. It also helps identify highly cited papers, active patent assignees, frequently mentioned technical directions, and possible gaps between academic research and industrial applications.

## Installation

```bash
pip install requests pandas python-dotenv tqdm
```

Optional dependency for LLM-enhanced mode:

```bash
pip install openai
```

## Usage

Basic usage:

```bash
python research_patent_survey_agent.py \
  --topic "GH4169 alloy additive manufacturing thermal simulation" \
  --max-papers 30 \
  --max-patents 20 \
  --out ./output
```

Enable LLM-enhanced mode:

```bash
export OPENAI_API_KEY="your_api_key"

python research_patent_survey_agent.py \
  --topic "nickel-based superalloy additive manufacturing" \
  --use-llm
```

For Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your_api_key"
```

## Output

After execution, the output directory will contain:

```text
output/
├── survey_report.md
├── papers.csv
├── patents.csv
└── raw_result.json
```

### File Description

| File               | Description                                        |
| ------------------ | -------------------------------------------------- |
| `survey_report.md` | Final structured research and patent survey report |
| `papers.csv`       | Ranked academic paper results                      |
| `patents.csv`      | Ranked patent results                              |
| `raw_result.json`  | Complete raw structured data                       |

## Example Use Cases

This project can be used for:

* Literature review before thesis topic selection
* Research proposal preparation
* Technology scouting
* Patent landscape analysis
* R&D project planning
* Competitive technology analysis
* Early-stage scientific investigation
* Academic group meeting preparation
* Technical report generation

## Tech Stack

* Python
* Requests
* Pandas
* TQDM
* python-dotenv
* OpenAlex API
* Crossref API
* PatentsView API
* OpenAI API, optional

## Project Value

The system can reduce a research and patent investigation task from several hours or days to a few minutes. It helps users quickly understand the current state of a technical field, identify important papers and patents, and generate a reusable structured report.

By combining literature search, patent search, relevance ranking, and automated report generation, the project provides a practical foundation for building more advanced research intelligence systems.

## Future Improvements

Planned extensions include:

* Support for more academic databases such as Semantic Scholar, arXiv, PubMed, Scopus, and Web of Science
* Support for more patent databases such as Google Patents, Lens, Derwent, Incopat, and Patsnap
* Full-text PDF parsing
* Patent claim analysis
* Citation network analysis
* Technology roadmap generation
* Streamlit or Flask web interface
* Knowledge graph construction
* Multi-turn conversational research assistant
* Automatic generation of literature review drafts




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

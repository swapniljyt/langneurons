# LangNeurons Swarm Framework 🧠🕸️

LangNeurons is a state-of-the-art, production-ready multi-agent orchestration framework designed for building **hierarchical agentic swarms**. Unlike flat agent structures that suffer from prompt-dilution and context clutter, LangNeurons structures agents under designated supervisor nodes to establish strict reporting lines, enhancing performance on complex tasks.

---

## 🚀 Quick Setup & Installation

### 1. Run Setup Script
Initialize the Python virtual environment, install package dependencies, and verify local Redis settings.
```bash
./setup.sh
```

### 2. Configure Environment Credentials
Credentials are saved locally in the `langneurons/.env` configuration file on your machine.
Configure your LLM provider API keys and Redis connection parameters:
```env
# LLM Providers
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key
MOONSHOT_API_KEY=your_moonshot_api_key
OPENROUTER_API_KEY=your_openrouter_api_key

# Model Selection
ROUTER_MODEL=gpt-4o
THINKING_MODEL=gemini-1.5-pro

# Database Configuration
REDIS_URL=redis://localhost:6379/0
```

### 3. Launch the Application
Start the FastAPI server and the interactive visual dashboard:
```bash
./run.sh
```
Open your browser and navigate to `http://localhost:8000` to launch the **Synapse Agent Console**.

---

## ✨ Framework Benefits & Key Features

*   🔒 **Local Sovereignty (Privacy First)**: All conversation traces, execution outputs, and agent parameters reside strictly in your local Redis databases. No telemetry is harvested.
*   🧠 **Isolated Context Window**: Each agent maintains its own localized context, preventing prompt leakage and memory dilution as tool counts increase.
*   🎯 **Selective Tool Activation**: The supervisor orchestrator determines which node is activated, significantly reducing token usage and latency.
*   ⚡ **Deterministic Execution**: Seamlessly compile visual canvas hierarchies into clean Python scripts using native state checkpointing.
*   🔄 **Dynamic Script Lifecycle**: Execution scripts are compiled, run in sandboxed subprocesses, and automatically cleaned up from disk upon swarm exit.

---

## 🛠️ How to Use (Step-by-Step Guide)

1.  **Orchestrate Your Swarm**: Open the canvas dashboard, drag and connect agent nodes (e.g., Coordinator, Researcher, QA Developer).
2.  **Assign Capability Tools**: Assign selective tool scopes to child agents.
3.  **Compile & Preview Code**: Click the **Swarm Code** tab to inspect the generated Python swarm configuration.
4.  **Execute & Live Stream**: Launch a chat session. Watch the **Thinking/Tooling Spinner** run constantly during process orchestration, and inspect clean markdown outputs when final responses are returned.

---

## 💡 What You Should Build

*   🛒 **E-Commerce Automation Swarms**: Construct a hierarchical manager agent that delegates order processing to a developer, stock check to an inventory search agent, and draft verification to a QA specialist.
*   📰 **Multi-Agent Research Clusters**: Build an editor node that coordinates search agents, content synthesizers, and fact-checkers to write comprehensive research summaries.
*   📈 **Real-Time Data Pipeline Pipelines**: Spin up specialized tooling agents for API pulling, DB writing, and analytics calculations under a single coordinator.

---

## 📞 Creator & Maintainer Contacts

For enterprise support, integrations, or contributions, feel free to reach out to the project creator:

*   👤 **Author**: Swapnil Jyot
*   📞 **Phone**: `+91 6394438455`
*   📧 **Email**: [swapniljytkd888@gmail.com](mailto:swapniljytkd888@gmail.com)
*   💻 **GitHub**: [github.com/swapniljyt](https://github.com/swapniljyt)
*   🔗 **LinkedIn**: [linkedin.com/in/swapniljyot](https://www.linkedin.com/in/swapniljyot)

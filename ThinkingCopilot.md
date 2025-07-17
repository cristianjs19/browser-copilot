# 🧠 [Thinking Copilot](https://github.com/cristianjs19/browser-copilot)

This is a fork of the [Abstracta](https://abstracta.us/) project [Browser Copilot](https://github.com/abstracta/browser-copilot):  
*An browser extension that brings AI reasoning directly to your browsing experience*

<img src="https://i.imgur.com/onE07aa.png" alt="agent-thinking" width="240" height="400">

---

## 🚀 Quick Start

- Clone the project accessing to this [repository](https://github.com/cristianjs19/browser-copilot)

### 📋 Prerequisites
- 🐳 **Docker** + **Docker Compose**
- 🌐 **Chrome browser** (recent version)

### ⚙️ Setup

#### 🔧 Backend Server
1. **Configure environment**: Set up your `.env` file in the `/agent-thinking` directory based on the `sample.env` example
2. **Navigate to directory**: Open your bash console and navigate to `/BROWSER-COPILOT/agent-thinking`
3. **Launch server**: Run `docker-compose up --build`

#### 🔌 Browser Extension
1. **Open Extensions**: Go to Chrome's Extension manager → "My extensions" section (`chrome://extensions/`)
2. **Enable Developer Mode**: Turn on developer mode
3. **Install Extension**: Drag and drop the `browser-copilot-dev.zip` file into the extensions page
4. **Connect to Server**: Click "Add Copilot" and add the server URL: `http://localhost:8000`

---

## 🧪 Testing

### 🎨 Frontend Tests
```bash
cd /browser-extension
pnpm install
pnpm test:run
```

### 🔬 Backend Tests
*Ensure the backend server is running first*
```bash
docker exec agent_thinking poetry run pytest tests/
```

---

## ✨ Features

This agent is an extension of the agent-extended copilot that integrates with Google Gemini API and provides some extra features like:

- ✅ Accessing a reasoner version of the model called "thinking mode"
- ✅ Be able to alternate between both modes within the same conversation without losing the context
- ✅ Access to the thought process detail on the "thinking mode"
- ✅ A standard response model applied to all 'chat' endpoints and different agents, making it easier to provide additional information about the agent's response, such as tokens consumed during the interaction, and distinguishing between a 'standard' content response and 'thoughts'
- ✅ A "stop button" that allows the user to stop the response streaming process
- ✅ Information about the consumed tokens on each interaction, including the detail of the "standard" response tokens and the tokens spent on the thought process
- ✅ Configure the front end client to enable the "thinking mode" feature by including the capability "has_thinking_mode" to the manifest.json file
- ✅ A collapsible element that allows to observe a summary of the thought process steps the agent applied to analyze the user query
- ✅ When unfolded, the collapsible element shows the entire thought process applied by the agent
- ✅ Hot reload for the backend server to enhance the development experience

This agent also provides an example on how to automate basic flows with the copilot, providing an example automation to navigate to abstracta.us contact site and filling the full name field.

- ✅ A test battery to validate some key aspects of its functioning on the front end and the back end as well

On top of the existing ones, including: authentication, proper session handling, response streaming, and transcripts support.

---

*Ready to enhance your browsing experience with AI-powered reasoning? Get started above! 🚀*
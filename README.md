# SIWRA Pension Advisor System

A multi-agent pension advisor system built with LangGraph that provides personalized pension advice through a conversational interface.

## System Overview

The SIWRA Pension Advisor is a sophisticated multi-agent system designed to:

1. Gather user information through natural conversation
2. Analyze pension needs based on user profiles
3. Generate personalized pension advice
4. Track API usage costs
5. Handle errors gracefully with user-friendly messages

## Key Components

### Agent Architecture

The system uses a multi-agent architecture with specialized agents:

- **Conversational Agent**: Friendly interface for gathering user information
- **Pension Analyst Agent**: Expert for analyzing needs and generating advice
- **Calculation Agent**: Specialized for pension calculations
- **Error Analyzer**: Handles errors and provides user-friendly messages

### Conversation Personality

The system features a warm, engaging personality:

- Uses positive, confident language with a personal touch
- Avoids technical disclaimers like "As an AI..."
- Incorporates compliments and shows enthusiasm
- Keeps responses concise (2-3 sentences maximum)
- Specifically mentions AKAP-KR and other pension agreements when relevant

### Conversation Persistence

The system maintains conversation context across multiple interactions:

- Session management for both REST API and WebSocket connections
- Client IP-based session tracking for REST requests
- UUID-based session tracking for WebSocket connections
- Automatic cleanup of inactive sessions

### Cost Tracking

The system includes robust cost tracking capabilities:

- Logs all API usage with detailed metrics
- Monitors budget thresholds with alerts
- Generates usage reports by agent and action
- Prevents budget overruns

### Error Handling

Advanced error handling features:

- Classifies errors into types (MISSING_INFO, CALCULATION_ERROR, SYSTEM_ERROR)
- Provides user-friendly messages in Swedish
- Updates a presentation database with missing information patterns
- Enables graceful recovery from errors

### Presentation Database

A database for improving user interactions:

- Stores important information factors and question templates
- Tracks frequency of missing information
- Guides future conversations based on historical data

### Comprehensive Logging

Enhanced logging system for easier debugging:

- Detailed DEBUG level logging to file and console
- Full state logging before and after message processing
- Improved error handling with full stack traces
- WebSocket error handling with better context

### Automatic Port Management

Intelligent port handling for smoother server operation:

- Detects and kills processes using port 9090 before starting
- Works on both Windows and Linux/Mac systems
- Includes retry logic if the port is still in use
- Provides clear logging about port management

## Getting Started

### Prerequisites

- Python 3.8+
- OpenAI API key

### Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   ```
   cp .env.example .env
   ```
   Then edit the `.env` file with your API keys

### Running the Server

Start the server using the run script:

```
python run.py
```

The script will automatically handle port management and start the server at http://127.0.0.1:9090

## API Endpoints

### REST API

- `POST /chat`: Send a message and receive a response
  - Request body: `{"message": "Your question here"}`
  - Response: `{"response": "Answer from the advisor"}`
  - Maintains conversation context across multiple requests

### WebSocket API

- `ws://127.0.0.1:9090/ws`: Real-time chat interface
  - Send text messages directly
  - Receive text responses
  - Maintains full conversation context until disconnection

## Workflow Visualization

The system includes a visualization tool to understand the agent workflow:

```
python visualize_workflow.py
```

This will generate a `workflow.png` file showing the agent interactions.

## Error Codes and Recovery

| Error Type | Description | Recovery Strategy |
|------------|-------------|-------------------|
| MISSING_INFO | User needs to provide more information | Ask specific questions |
| CALCULATION_ERROR | Error in pension calculations | Retry with different parameters |
| SYSTEM_ERROR | Internal system error | Restart conversation |

## Budget Monitoring

The system monitors API usage costs with the following thresholds:

- Daily budget: $5
- Monthly budget: $100

Alerts are generated when usage approaches these limits.

## Recent Improvements

- **Enhanced Personality**: Warm, confident responses that build rapport with users
- **Conversation Persistence**: Maintains context across multiple messages
- **Vector Store Integration**: Queries relevant pension documents for accurate responses
- **Improved Logging**: Comprehensive logging for easier debugging
- **Automatic Port Management**: Smoother server startup and operation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
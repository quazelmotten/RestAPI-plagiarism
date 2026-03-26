# Plagiarism Detection Frontend

A React SPA frontend for the Plagiarism Detection API built with React 18, TypeScript, Vite, and Chakra UI.

## Features

- **Teacher Dashboard**: Overview, Students, Submissions, Plagiarism Graph, and Upload pages
- **Plagiarism Visualization**: Interactive network graph using Cytoscape.js
- **File Upload**: Drag & drop file uploads with multiple file support
- **Responsive Design**: Mobile-friendly interface

## Tech Stack

- **React 18** + TypeScript
- **Vite** - Build tool
- **Chakra UI v2** - Component library
- **React Router v6** - Navigation
- **TanStack Query** - Data fetching
- **Cytoscape.js** - Network graph visualization
- **React Dropzone** - File uploads
- **Axios** - HTTP client

## Quick Start

### Development

```bash
cd frontend
npm install
npm run dev
```

The dev server starts at `http://localhost:5173`

### Production Build

```bash
npm run build
```

Output goes to `dist/` folder

## Project Structure

```
frontend/
├── src/
│   ├── components/     # Reusable components (Sidebar, Header)
│   ├── pages/          # Page components
│   │   ├── Dashboard.tsx
│   │   ├── Overview.tsx
│   │   ├── Students.tsx
│   │   ├── Submissions.tsx
│   │   ├── PlagiarismGraph.tsx
│   │   └── Upload.tsx
│   ├── services/       # API client
│   ├── types/          # TypeScript types
│   ├── App.tsx         # Main app
│   └── main.tsx        # Entry point
└── dist/               # Build output
```

## Configuration

### Environment Variables

Create `.env` in `frontend/`:

```env
VITE_API_URL=http://localhost:8000
```

### API Endpoints Expected

The frontend expects these FastAPI endpoints:

- `GET /plagiarism/check` - Submit files for plagiarism check
- `GET /plagiarism/tasks` - List all tasks
- `GET /plagiarism/{task_id}/results` - Get task results
- `GET /plagiarism/files` - List files
- `GET /plagiarism/files/{file_id}/content` - Get file content
- `GET /plagiarism/network` - Get plagiarism graph data

## Available Scripts

- `npm run dev` - Development server
- `npm run build` - Production build
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Docker Integration

The `api.Dockerfile` includes a multi-stage build that:
1. Builds the React frontend
2. Copies it into the Python container
3. Serves both API and frontend on port 8000

## Key Components

### Plagiarism Graph
Interactive network visualization showing connections between similar submissions:
- Color-coded edges: Red (≥80%), Yellow (60-79%), Green (<60%)
- Adjustable similarity threshold
- Force-directed layout

### Upload Files
- Drag & drop interface
- Multiple file selection
- Language selection
- Progress tracking

## Next Steps

1. Connect frontend to real API endpoints
2. Add loading states and error handling
3. Implement pagination for tables
4. Add export functionality

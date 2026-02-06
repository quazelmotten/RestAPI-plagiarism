# Plagiarism Detection Frontend

A React SPA frontend for the Plagiarism Detection API built with React 18, TypeScript, Vite, and Chakra UI.

## Features

- **Authentication**: JWT-based auth with protected routes
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
│   ├── components/     # Reusable components (Sidebar, Header, PrivateRoute)
│   ├── contexts/       # React contexts (AuthContext)
│   ├── pages/          # Page components
│   │   ├── Login.tsx
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

- `POST /auth/login` - Login, returns JWT
- `GET /auth/me` - Get current user
- `GET /students` - List students
- `GET /submissions` - List submissions
- `POST /submissions` - Upload files
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

### Authentication
- JWT token stored in localStorage
- Auto-redirect on token expiration
- Protected routes

## Next Steps

1. Implement FastAPI endpoints for auth, students, and submissions
2. Connect frontend to real API endpoints
3. Add loading states and error handling
4. Implement pagination for tables
5. Add export functionality

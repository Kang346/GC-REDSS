# GC-REDSS Frontend

Interactive web frontend for the Geo-Circle Based Real Estate Decision Support System.

## Features

- 🗺️ **Interactive Map**: View properties on NYC map with markers colored by score
- 🔍 **Search & Filter**: Search properties by work address with customizable thresholds
- 📊 **Score Visualization**: Radar charts and bar charts showing detailed score breakdown
- 🏠 **Property Details**: Click on any property to see detailed information
- ⚙️ **Weight Adjustment**: Customize scoring weights in real-time
- 📋 **Property List**: Sidebar list of all properties sorted by score

## Installation

```bash
cd frontend
npm install
```

## Development

```bash
# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Prerequisites

Make sure the backend API is running on `http://localhost:5000`:

```bash
# In the project root directory
python src/api.py
```

## Usage

1. Start the backend API server
2. Start the frontend development server (`npm run dev`)
3. Open `http://localhost:3000` in your browser
4. Enter a work address and click "Search Properties"
5. Click on any property marker or list item to see details

## Project Structure

```
frontend/
├── src/
│   ├── components/       # React components
│   │   ├── MapView.tsx   # Main map component
│   │   ├── SearchForm.tsx # Search form
│   │   ├── PropertyList.tsx # Property list sidebar
│   │   └── PropertyDetail.tsx # Property detail panel
│   ├── services/         # API services
│   │   └── api.ts        # API client
│   ├── store/            # State management
│   │   └── propertyStore.ts # Zustand store
│   ├── types/            # TypeScript types
│   │   └── index.ts      # Type definitions
│   ├── App.tsx           # Main app component
│   └── main.tsx          # Entry point
├── package.json
└── vite.config.ts
```





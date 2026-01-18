# AIS Viewer Mobile App

React Native mobile application for viewing vessel positions in real-time.


https://github.com/user-attachments/assets/eaa60632-9a3e-4f53-a236-82e0fced79cd


## Features

- Mapbox map integration
- 10-second HTTP polling for vessel updates
- Delta updates (only fetch changed vessels)
- Zoom level enforcement (>= 12)
- Vessel markers with course indicators
- React Context API for state management

## Prerequisites

- Node.js 18+
- Expo CLI
- iOS Simulator (Mac) or Android Emulator
- Mapbox API token

## Setup

1. Install dependencies:
```bash
cd mobile

# Fix npm cache issues if needed:
sudo chown -R $USER:$(id -gn $USER) ~/.npm

# Install dependencies
npm install
```

2. Configure environment variables:

Create `.env` file in the `mobile` directory:
```bash
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000
EXPO_PUBLIC_MAPBOX_TOKEN=your_mapbox_token_here
```

Get a Mapbox token from: https://account.mapbox.com/access-tokens/

3. Run the app:
```bash
# Start Expo dev server
npm start

# Run on iOS
npm run ios

# Run on Android
npm run android
```

## Project Structure

```
mobile/
├── src/
│   ├── components/
│   │   └── VesselMap.tsx        # Main map component
│   ├── contexts/
│   │   └── VesselContext.tsx    # React Context for state
│   ├── services/
│   │   └── VesselApiService.ts  # API client
│   ├── utils/
│   │   └── geohash.ts           # Geohash utilities
│   ├── types.ts                 # TypeScript types
│   └── config.ts                # Configuration
├── App.tsx                      # Main app component
└── package.json
```

## Configuration

Edit `src/config.ts` to change:
- API base URL
- Mapbox token
- Polling interval (default: 10 seconds)
- Min zoom level (default: 12)
- Default map center

## API Endpoint

The app polls the following endpoint every 10 seconds:

```
GET /api/vessels?bbox=minLon,minLat,maxLon,maxLat&zoom=12&lastUpdateTime=ISO8601
```

## Development

- TypeScript strict mode enabled
- React Context API for state management (no external libraries)
- Mapbox SDK for map rendering
- Axios for HTTP requests

## Troubleshooting

### npm install fails with permission errors

Fix npm cache permissions:
```bash
sudo chown -R $USER:$(id -gn $USER) ~/.npm
npm cache clean --force
npm install
```

### Mapbox not showing

1. Check that `EXPO_PUBLIC_MAPBOX_TOKEN` is set in `.env`
2. Verify token is valid at https://account.mapbox.com
3. Restart Expo dev server after changing `.env`

### No vessels showing

1. Check zoom level is >= 12
2. Verify API service is running (`http://localhost:8000/health`)
3. Check device/simulator can reach localhost (use ngrok for physical devices)
4. Check browser console for errors


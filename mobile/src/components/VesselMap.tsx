/**
 * Vessel Map Component
 */
import React, { useEffect, useRef, useState, useCallback } from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import MapboxGL from "@rnmapbox/maps";
import { useVessels } from "../contexts/VesselContext";
import { VesselApiService } from "../services/VesselApiService";
import {
  MAPBOX_ACCESS_TOKEN,
  DEFAULT_MAP_CENTER,
  DEFAULT_MAP_ZOOM,
  MIN_ZOOM_LEVEL,
  POLL_INTERVAL_MS,
  VESSELS_MAX_ZOOM_LEVEL,
} from "../config";
import { Bbox } from "../types";

if (MAPBOX_ACCESS_TOKEN) {
  MapboxGL.setAccessToken(MAPBOX_ACCESS_TOKEN);
} else {
  console.error("MAPBOX_ACCESS_TOKEN is not set!");
}

export const VesselMap: React.FC = () => {
  if (!MAPBOX_ACCESS_TOKEN || MAPBOX_ACCESS_TOKEN === "") {
    return (
      <View style={styles.container}>
        <View style={styles.errorContainer}>
          <Text style={styles.errorTitle}>Configuration Error</Text>
          <Text style={styles.errorText}>
            Mapbox access token is not set.{"\n\n"}
            Please create a .env file in the mobile directory with:{"\n"}
            EXPO_PUBLIC_MAPBOX_TOKEN=your_token_here
          </Text>
        </View>
      </View>
    );
  }

  const {
    vessels,
    lastServerTime,
    updateMultipleVessels,
    clearAll,
    setLastServerTime,
  } = useVessels();

  const [zoom, setZoom] = useState(DEFAULT_MAP_ZOOM);
  const [bbox, setBbox] = useState<Bbox | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedVessel, setSelectedVessel] = useState<number | null>(null);

  const mapRef = useRef<MapboxGL.MapView>(null);
  const cameraRef = useRef<MapboxGL.Camera>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const lastServerTimeRef = useRef<string | null>(null);

  useEffect(() => {
    lastServerTimeRef.current = lastServerTime;
    console.log("Last server time:", lastServerTime);
  }, [lastServerTime]);

  const handleZoomIn = useCallback(() => {
    if (cameraRef.current) {
      cameraRef.current.zoomTo(zoom + 1, 300);
    }
  }, [zoom]);

  const handleZoomOut = useCallback(() => {
    if (cameraRef.current) {
      cameraRef.current.zoomTo(zoom - 1, 300);
    }
  }, [zoom]);

  const handleVesselTap = useCallback((event: any) => {
    const feature = event?.features?.[0];
    if (feature?.properties?.mmsi) {
      setSelectedVessel(feature.properties.mmsi);
    }
  }, []);

  const handleCloseVesselInfo = useCallback(() => {
    setSelectedVessel(null);
  }, []);

  const fetchVessels = useCallback(async () => {
    if (!bbox || zoom < VESSELS_MAX_ZOOM_LEVEL) {
      return;
    }

    try {
      setError(null);

      const response = await VesselApiService.fetchVessels(
        bbox,
        Math.round(zoom),
        lastServerTimeRef.current ?? undefined
      );

      console.log(
        `API Response: ${response.vessels.length} vessels, delta=${response.is_delta}`
      );
      if (response.vessels.length > 0) {
        updateMultipleVessels(response.vessels);
      }

      setLastServerTime(response.server_time);
    } catch (err) {
      console.error("Error fetching vessels:", err);
      setError("Failed to fetch vessels");
    }
  }, [bbox, zoom, updateMultipleVessels, setLastServerTime]);

  const handleRegionDidChange = useCallback(async () => {
    try {
      const bounds = await mapRef.current?.getVisibleBounds();
      const currentZoom = await mapRef.current?.getZoom();

      if (!bounds || !currentZoom) return;

      setZoom(currentZoom);

      // Mapbox getVisibleBounds returns [[southwest], [northeast]]
      // southwest = [minLon/west, minLat/south]
      // northeast = [maxLon/east, maxLat/north]
      const newBbox: Bbox = {
        minLon: Math.min(bounds[0][0], bounds[1][0]),
        minLat: Math.min(bounds[0][1], bounds[1][1]),
        maxLon: Math.max(bounds[0][0], bounds[1][0]),
        maxLat: Math.max(bounds[0][1], bounds[1][1]),
      };

      // Only update bbox if it actually changed (prevents unnecessary re-fetches)
      setBbox((prevBbox) => {
        if (
          prevBbox &&
          Math.abs(prevBbox.minLon - newBbox.minLon) < 0.0001 &&
          Math.abs(prevBbox.minLat - newBbox.minLat) < 0.0001 &&
          Math.abs(prevBbox.maxLon - newBbox.maxLon) < 0.0001 &&
          Math.abs(prevBbox.maxLat - newBbox.maxLat) < 0.0001
        ) {
          return prevBbox;
        }
        return newBbox;
      });

      if (currentZoom < VESSELS_MAX_ZOOM_LEVEL) {
        clearAll();
      }
    } catch (err) {
      console.error("Error handling region change:", err);
    }
  }, [clearAll]);

  useEffect(() => {
    if (bbox && zoom >= VESSELS_MAX_ZOOM_LEVEL) {
      setLastServerTime(null);
      setTimeout(() => fetchVessels(), 10);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bbox]);

  useEffect(() => {
    if (zoom < VESSELS_MAX_ZOOM_LEVEL) {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      return;
    }

    if (!pollingIntervalRef.current) {
      pollingIntervalRef.current = setInterval(() => {
        fetchVessels();
        // removeStaleVessels();
      }, POLL_INTERVAL_MS);
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoom >= VESSELS_MAX_ZOOM_LEVEL]);

  const vesselGeoJSON = React.useMemo(() => {
    const features = Array.from(vessels.values()).map((vessel) => ({
      type: "Feature" as const,
      id: vessel.mmsi,
      geometry: {
        type: "Point" as const,
        coordinates: [vessel.longitude, vessel.latitude],
      },
      properties: {
        mmsi: vessel.mmsi,
        course: vessel.course ?? 0,
        adjustedCourse: (vessel.course ?? 0) - 90, // Adjust course for arrow rotation
        speed: vessel.speed ?? 0,
        ship_type: vessel.ship_type ?? 0,
        last_updated: vessel.last_updated,
      },
    }));

    console.log(
      `Visible vessels: ${features.length} (total cached: ${vessels.size})`
    );

    return {
      type: "FeatureCollection" as const,
      features,
    };
  }, [vessels, bbox]);

  return (
    <View style={styles.container}>
      <MapboxGL.MapView
        ref={mapRef}
        style={styles.map}
        onRegionDidChange={handleRegionDidChange}
      >
        <MapboxGL.Camera
          ref={cameraRef}
          zoomLevel={DEFAULT_MAP_ZOOM}
          centerCoordinate={[
            DEFAULT_MAP_CENTER.longitude,
            DEFAULT_MAP_CENTER.latitude,
          ]}
        />

        {zoom >= MIN_ZOOM_LEVEL && vessels.size > 0 && (
          <>
            <MapboxGL.ShapeSource
              id="vessels"
              shape={vesselGeoJSON}
              onPress={handleVesselTap}
            >
              <MapboxGL.CircleLayer
                id="vessel-circles"
                style={{
                  circleRadius: 7,
                  circleColor: [
                    "case",
                    [">", ["get", "speed"], 0.5],
                    "#10B981", // Green for moving vessels
                    "#6B7280", // Gray for stationary vessels
                  ],
                  circleStrokeWidth: 1,
                  circleStrokeColor: "#FFFFFF",
                  circleOpacity: 0.95,
                }}
              />

              <MapboxGL.SymbolLayer
                id="vessel-direction-text"
                style={{
                  textField: "↟",
                  textSize: 20,
                  textRotate: ["get", "course"],
                  textRotationAlignment: "map",
                  textColor: "#FFFFFF",
                  textAllowOverlap: true,
                  textIgnorePlacement: true,
                }}
              />
            </MapboxGL.ShapeSource>
          </>
        )}
      </MapboxGL.MapView>

      <View style={styles.zoomControls}>
        <TouchableOpacity
          style={styles.zoomButton}
          onPress={handleZoomIn}
          activeOpacity={0.7}
        >
          <Text style={styles.zoomButtonText}>+</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.zoomButton}
          onPress={handleZoomOut}
          activeOpacity={0.7}
        >
          <Text style={styles.zoomButtonText}>−</Text>
        </TouchableOpacity>
      </View>

      {/* Vessel Info Panel */}
      {selectedVessel && vessels.get(selectedVessel) && (
        <View style={styles.vesselInfoContainer}>
          <View style={styles.vesselInfoPanel}>
            <View style={styles.vesselInfoHeader}>
              <Text style={styles.vesselInfoTitle}>Vessel Information</Text>
              <TouchableOpacity
                onPress={handleCloseVesselInfo}
                style={styles.closeButton}
              >
                <Text style={styles.closeButtonText}>✕</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.vesselInfoContent}>
              {(() => {
                const vessel = vessels.get(selectedVessel)!;
                const updatedTime = new Date(vessel.last_updated);
                const timeAgo = Math.floor(
                  (Date.now() - updatedTime.getTime()) / 1000
                );

                return (
                  <>
                    <View style={styles.infoRow}>
                      <Text style={styles.infoLabel}>MMSI:</Text>
                      <Text style={styles.infoValue}>{vessel.mmsi}</Text>
                    </View>

                    <View style={styles.infoRow}>
                      <Text style={styles.infoLabel}>Position:</Text>
                      <Text style={styles.infoValue}>
                        {vessel.latitude.toFixed(4)}°,{" "}
                        {vessel.longitude.toFixed(4)}°
                      </Text>
                    </View>

                    {vessel.speed !== null && vessel.speed !== undefined && (
                      <View style={styles.infoRow}>
                        <Text style={styles.infoLabel}>Speed:</Text>
                        <Text style={styles.infoValue}>
                          {vessel.speed.toFixed(1)} knots
                        </Text>
                      </View>
                    )}

                    {vessel.course !== null && vessel.course !== undefined && (
                      <View style={styles.infoRow}>
                        <Text style={styles.infoLabel}>Course:</Text>
                        <Text style={styles.infoValue}>
                          {vessel.course.toFixed(0)}°
                        </Text>
                      </View>
                    )}

                    <View style={styles.infoRow}>
                      <Text style={styles.infoLabel}>Status:</Text>
                      <Text
                        style={[
                          styles.infoValue,
                          vessel.speed && vessel.speed > 0.5
                            ? styles.statusMoving
                            : styles.statusStationary,
                        ]}
                      >
                        {vessel.speed && vessel.speed > 0.5
                          ? "Moving"
                          : "Stationary"}
                      </Text>
                    </View>

                    <View style={styles.infoRow}>
                      <Text style={styles.infoLabel}>Last Updated:</Text>
                      <Text style={styles.infoValue}>
                        {timeAgo < 60
                          ? `${timeAgo}s ago`
                          : `${Math.floor(timeAgo / 60)}m ago`}
                      </Text>
                    </View>
                  </>
                );
              })()}
            </View>
          </View>
        </View>
      )}

      {/* Zoom warning */}
      {zoom < VESSELS_MAX_ZOOM_LEVEL && (
        <View style={styles.warningContainer}>
          <Text style={styles.warningText}>
            Zoom in to level {VESSELS_MAX_ZOOM_LEVEL} or higher to see vessels
          </Text>
        </View>
      )}

      {/* Status indicators */}
      <View style={styles.statusContainer}>
        <Text style={styles.statusText}>Zoom: {zoom.toFixed(1)}</Text>
        <Text style={styles.statusText}>Vessels: {vessels.size}</Text>
        <Text style={styles.statusText}>Min Zoom: {MIN_ZOOM_LEVEL}</Text>
        {error && <Text style={styles.errorText}>{error}</Text>}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  map: {
    flex: 1,
  },
  errorContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
    backgroundColor: "#f8f9fa",
  },
  errorTitle: {
    fontSize: 24,
    fontWeight: "bold",
    marginBottom: 16,
    color: "#dc3545",
  },
  warningContainer: {
    position: "absolute",
    bottom: 100,
    left: 20,
    right: 20,
    backgroundColor: "rgba(255, 193, 7, 0.9)",
    padding: 15,
    borderRadius: 8,
  },
  warningText: {
    color: "#000",
    fontSize: 14,
    textAlign: "center",
    fontWeight: "600",
  },
  statusContainer: {
    position: "absolute",
    top: 100,
    left: 20,
    backgroundColor: "rgba(0, 0, 0, 0.7)",
    padding: 10,
    borderRadius: 8,
  },
  statusText: {
    color: "#fff",
    fontSize: 12,
    textAlign: "left",
  },
  errorText: {
    fontSize: 16,
    textAlign: "center",
    color: "#6c757d",
    lineHeight: 24,
  },
  zoomControls: {
    position: "absolute",
    right: 20,
    top: "50%",
    marginTop: -50,
    gap: 10,
  },
  zoomButton: {
    width: 50,
    height: 50,
    backgroundColor: "rgba(255, 255, 255, 0.95)",
    borderRadius: 8,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 5,
  },
  zoomButtonText: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#333",
  },
  vesselInfoContainer: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  vesselInfoPanel: {
    backgroundColor: "#FFFFFF",
    borderRadius: 12,
    width: "100%",
    maxWidth: 400,
    shadowColor: "#000",
    shadowOffset: {
      width: 0,
      height: 4,
    },
    shadowOpacity: 0.3,
    shadowRadius: 4.65,
    elevation: 8,
  },
  vesselInfoHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#E5E7EB",
  },
  vesselInfoTitle: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#1F2937",
  },
  closeButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: "#F3F4F6",
    justifyContent: "center",
    alignItems: "center",
  },
  closeButtonText: {
    fontSize: 20,
    color: "#6B7280",
    fontWeight: "bold",
  },
  vesselInfoContent: {
    padding: 16,
  },
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#F3F4F6",
  },
  infoLabel: {
    fontSize: 14,
    color: "#6B7280",
    fontWeight: "600",
  },
  infoValue: {
    fontSize: 14,
    color: "#1F2937",
    fontWeight: "500",
  },
  statusMoving: {
    color: "#10B981",
    fontWeight: "bold",
  },
  statusStationary: {
    color: "#6B7280",
    fontWeight: "bold",
  },
});

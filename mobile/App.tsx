/**
 * AIS Viewer Mobile App
 */
import React from "react";
import { StyleSheet, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { VesselProvider } from "./src/contexts/VesselContext";
import { VesselMap } from "./src/components/VesselMap";

export default function App() {
  return (
    <VesselProvider>
      <View style={styles.container}>
        <StatusBar style="auto" />
        <VesselMap />
      </View>
    </VesselProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});

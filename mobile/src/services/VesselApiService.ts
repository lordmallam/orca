/**
 * API Service for fetching vessel data.
 */
import axios from "axios";
import { API_BASE_URL } from "../config";
import { VesselsResponse, Bbox } from "../types";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

export class VesselApiService {
  /**
   * Fetch vessels in viewport.
   */
  static async fetchVessels(
    bbox: Bbox,
    zoom: number,
    lastUpdateTime?: string
  ): Promise<VesselsResponse> {
    try {
      const bboxString = `${bbox.minLon},${bbox.minLat},${bbox.maxLon},${bbox.maxLat}`;

      const params: any = {
        bbox: bboxString,
        zoom,
      };

      if (lastUpdateTime) {
        params.lastUpdateTime = lastUpdateTime;
      }

      const response = await api.get<VesselsResponse>("/api/vessels", {
        params,
      });

      return response.data;
    } catch (error) {
      console.error("Error fetching vessels:", error);
      throw error;
    }
  }

  /**
   * Health check.
   */
  static async healthCheck(): Promise<boolean> {
    try {
      const response = await api.get("/health");
      return response.data.status === "healthy";
    } catch (error) {
      console.error("Health check failed:", error);
      return false;
    }
  }
}

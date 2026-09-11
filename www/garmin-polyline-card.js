/**
 * Garmin Activity Polyline Map Card
 * A simple custom Lovelace card to display activity routes from sensor attributes
 */

// Home Assistant proxies OpenStreetMap tiles through its own backend as of
// core 2026.9 (home-assistant/core#180441) — same origin as the card, so no
// CORS/Referer question, and OSM tile-usage-policy compliance is core's
// problem to solve once for every install, not ours to solve per card.
const MAP_TILES_RASTER_PATH = '/api/map_tiles/raster/{z}/{x}/{y}.png?token={token}';
// Core rotates the token every 30 min and keeps two live, so refreshing more
// often than that leaves margin for a slow round trip.
const MAP_TILES_TOKEN_REFRESH_MS = 20 * 60 * 1000;
const OSM_ATTRIBUTION = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
// Fallback for cores older than 2026.9, which have no /api/map_tiles proxy.
const OSM_DIRECT_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

class GarminPolylineCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._config = null;
    this._map = null;
    this._tileLayer = null;
    this._tokenRefreshInterval = null;
    this._polyline = null;
    this._initPending = false;
    this._lastPolylineKey = null;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('You need to define an entity');
    }
    this._config = {
      entity: config.entity,
      attribute: config.attribute || 'polyline',
      title: config.title || 'Activity Route',
      height: config.height || '300px',
      color: config.color || '#FF5722',
      weight: config.weight || 4,
      ...config
    };
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;

    // Only re-render when the relevant attribute actually changes
    const stateObj = hass.states[this._config.entity];
    const polylineData = stateObj?.attributes[this._config.attribute];
    const key = polylineData ? JSON.stringify(polylineData) : null;
    if (key === this._lastPolylineKey) return;
    this._lastPolylineKey = key;

    this._updateMap();
  }

  connectedCallback() {
    // Re-render when re-attached to the DOM (map was removed in disconnectedCallback)
    if (this._hass && this._config) {
      this._map = null;
      this._polyline = null;
      this._lastPolylineKey = null;
      this._updateMap();
    }
  }

  disconnectedCallback() {
    this._teardownMap();
  }

  _teardownMap() {
    clearInterval(this._tokenRefreshInterval);
    this._tokenRefreshInterval = null;
    if (this._map) {
      this._map.remove();
      this._map = null;
      this._tileLayer = null;
      this._polyline = null;
    }
  }

  _updateMap() {
    if (!this._hass || !this._config) return;

    const stateObj = this._hass.states[this._config.entity];
    if (!stateObj) return;

    const polylineData = stateObj.attributes[this._config.attribute];
    if (!polylineData || !Array.isArray(polylineData) || polylineData.length === 0) {
      this._renderNoData();
      return;
    }

    const coordinates = polylineData
      .filter(p => p.lat != null && p.lon != null)
      .map(p => [p.lat, p.lon]);

    if (coordinates.length === 0) {
      this._renderNoData();
      return;
    }

    this._renderMap(coordinates, stateObj);
  }

  _renderNoData() {
    this._teardownMap();
    this.shadowRoot.innerHTML = `
      <ha-card header="${this._config.title}">
        <div style="padding: 16px; text-align: center; color: var(--secondary-text-color);">
          No route data available
        </div>
      </ha-card>
    `;
  }

  _renderMap(coordinates, stateObj) {
    const activityName = stateObj.attributes.activity_name || stateObj.state || 'Activity';

    if (this._map) {
      // Update existing map — guard against Leaflet not being ready
      try {
        if (this._polyline) {
          this._polyline.setLatLngs(coordinates);
          this._map.invalidateSize();
          this._map.fitBounds(this._polyline.getBounds(), { padding: [20, 20] });
        }
      } catch (_e) {
        // Map pane not ready; tear down and rebuild
        this._teardownMap();
        this._renderMap(coordinates, stateObj);
      }
      return;
    }

    this.shadowRoot.innerHTML = `
      <ha-card header="${this._config.title}">
        <div id="map" style="height: ${this._config.height}; width: 100%;"></div>
        <div style="padding: 8px 16px; font-size: 12px; color: var(--secondary-text-color);">
          ${activityName} • ${coordinates.length} points
        </div>
      </ha-card>
      <link rel="stylesheet" href="/local/leaflet.css" />
    `;

    if (!window.L) {
      if (this._initPending) return;
      this._initPending = true;
      const script = document.createElement('script');
      script.src = '/local/leaflet.js';
      script.onload = () => {
        this._initPending = false;
        this._initMapWhenReady(coordinates);
      };
      script.onerror = () => {
        this._initPending = false;
        console.error('garmin-polyline-card: failed to load Leaflet from CDN');
      };
      document.head.appendChild(script);
    } else {
      this._initMapWhenReady(coordinates);
    }
  }

  _initMapWhenReady(coordinates, retries = 0) {
    const MAX_RETRIES = 10;
    requestAnimationFrame(() => {
      const mapContainer = this.shadowRoot.getElementById('map');
      if (!mapContainer || !window.L) return;

      if (mapContainer.offsetWidth === 0 || mapContainer.offsetHeight === 0) {
        if (retries < MAX_RETRIES) {
          this._initMapWhenReady(coordinates, retries + 1);
        }
        return;
      }

      this._initMap(coordinates);
    });
  }

  _initMap(coordinates) {
    const mapContainer = this.shadowRoot.getElementById('map');
    if (!mapContainer || !window.L) return;

    this._teardownMap();

    this._map = L.map(mapContainer, {
      zoomControl: true,
      scrollWheelZoom: false
    });

    this._addTileLayer();

    this._polyline = L.polyline(coordinates, {
      color: this._config.color,
      weight: this._config.weight,
      opacity: 0.8
    }).addTo(this._map);

    // Defer so the browser has painted the container before Leaflet measures it
    setTimeout(() => {
      try {
        if (this._map && this._polyline) {
          this._map.invalidateSize();
          this._map.fitBounds(this._polyline.getBounds(), { padding: [20, 20] });
        }
      } catch (_e) {
        // Map pane not fully laid out yet — safe to ignore
      }
    }, 50);

    if (coordinates.length > 0) {
      L.circleMarker(coordinates[0], {
        radius: 8,
        color: '#4CAF50',
        fillColor: '#4CAF50',
        fillOpacity: 1
      }).addTo(this._map).bindPopup('Start');

      L.circleMarker(coordinates[coordinates.length - 1], {
        radius: 8,
        color: '#F44336',
        fillColor: '#F44336',
        fillOpacity: 1
      }).addTo(this._map).bindPopup('End');
    }
  }

  async _fetchMapTilesToken() {
    if (!this._hass?.connection) return null;
    try {
      const result = await this._hass.connection.sendMessagePromise({ type: 'map_tiles/access_token' });
      return typeof result?.token === 'string' && result.token ? result.token : null;
    } catch (_e) {
      // Core predates the map_tiles proxy (pre-2026.9), or the websocket isn't ready
      return null;
    }
  }

  async _addTileLayer() {
    const targetMap = this._map;
    const token = await this._fetchMapTilesToken();
    if (this._map !== targetMap) return; // map was torn down/rebuilt while awaiting

    if (token) {
      this._tileLayer = L.tileLayer(MAP_TILES_RASTER_PATH, {
        attribution: OSM_ATTRIBUTION,
        maxZoom: 19,
        token
      }).addTo(targetMap);
      this._scheduleTokenRefresh();
      return;
    }

    // Fallback: connect to OSM directly. strict-origin-when-cross-origin
    // sends only the page origin as Referer — satisfies OSM's tile usage
    // policy without leaking the full local dashboard path.
    const DirectTileLayer = L.TileLayer.extend({
      createTile(coords, done) {
        const tile = document.createElement('img');
        tile.referrerPolicy = 'strict-origin-when-cross-origin';  // must be before src
        L.DomEvent.on(tile, 'load', L.Util.bind(this._tileOnLoad, this, done, tile));
        L.DomEvent.on(tile, 'error', L.Util.bind(this._tileOnError, this, done, tile));
        tile.alt = '';
        tile.setAttribute('role', 'presentation');
        tile.src = this.getTileUrl(coords);
        return tile;
      }
    });
    this._tileLayer = new DirectTileLayer(OSM_DIRECT_URL, {
      attribution: OSM_ATTRIBUTION,
      maxZoom: 19
    }).addTo(targetMap);
  }

  _scheduleTokenRefresh() {
    clearInterval(this._tokenRefreshInterval);
    this._tokenRefreshInterval = setInterval(async () => {
      const token = await this._fetchMapTilesToken();
      if (token && this._tileLayer) {
        this._tileLayer.options.token = token;
        this._tileLayer.redraw();
      }
    }, MAP_TILES_TOKEN_REFRESH_MS);
  }

  getCardSize() {
    return 4;
  }

  static getStubConfig() {
    return {
      entity: '',
      attribute: 'polyline',
      title: 'Activity Route'
    };
  }
}

customElements.define('garmin-polyline-card', GarminPolylineCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'garmin-polyline-card',
  name: 'Garmin Polyline Card',
  description: 'Display Garmin activity routes on a map'
});

console.info('%c GARMIN-POLYLINE-CARD %c loaded ', 'background: #FF5722; color: white;', '');

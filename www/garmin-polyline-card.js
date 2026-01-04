/**
 * Garmin Activity Polyline Map Card
 * A simple custom Lovelace card to display activity routes from sensor attributes
 */
class GarminPolylineCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._config = null;
    this._map = null;
    this._polyline = null;
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
    this._updateMap();
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

    // Convert to Leaflet format [[lat, lon], ...]
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
    this.shadowRoot.innerHTML = `
      <ha-card header="${this._config.title}">
        <div style="padding: 16px; text-align: center; color: var(--secondary-text-color);">
          No route data available
        </div>
      </ha-card>
    `;
    this._map = null;
  }

  _renderMap(coordinates, stateObj) {
    const activityName = stateObj.state || 'Activity';
    
    // Check if we already have a map container
    if (!this._map) {
      this.shadowRoot.innerHTML = `
        <ha-card header="${this._config.title}">
          <div id="map" style="height: ${this._config.height}; width: 100%;"></div>
          <div style="padding: 8px 16px; font-size: 12px; color: var(--secondary-text-color);">
            ${activityName} • ${coordinates.length} points
          </div>
        </ha-card>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
      `;

      // Load Leaflet if not already loaded
      if (!window.L) {
        const script = document.createElement('script');
        script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
        script.onload = () => this._initMap(coordinates);
        document.head.appendChild(script);
      } else {
        setTimeout(() => this._initMap(coordinates), 100);
      }
    } else {
      // Update existing polyline
      if (this._polyline) {
        this._polyline.setLatLngs(coordinates);
        this._map.fitBounds(this._polyline.getBounds(), { padding: [20, 20] });
      }
    }
  }

  _initMap(coordinates) {
    const mapContainer = this.shadowRoot.getElementById('map');
    if (!mapContainer || !window.L) return;

    // If map already exists, remove it first
    if (this._map) {
      this._map.remove();
      this._map = null;
    }

    // Create map
    this._map = L.map(mapContainer, {
      zoomControl: true,
      scrollWheelZoom: false
    });

    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap'
    }).addTo(this._map);

    // Add polyline
    this._polyline = L.polyline(coordinates, {
      color: this._config.color,
      weight: this._config.weight,
      opacity: 0.8
    }).addTo(this._map);

    // Fit map to polyline bounds
    this._map.fitBounds(this._polyline.getBounds(), { padding: [20, 20] });

    // Add start/end markers
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

  getCardSize() {
    return 4;
  }

  static getStubConfig() {
    return {
      entity: 'sensor.garmin_connect_last_activity',
      attribute: 'polyline',
      title: 'Activity Route'
    };
  }
}

customElements.define('garmin-polyline-card', GarminPolylineCard);

// Register with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'garmin-polyline-card',
  name: 'Garmin Polyline Card',
  description: 'Display Garmin activity routes on a map'
});

console.info('%c GARMIN-POLYLINE-CARD %c loaded ', 'background: #FF5722; color: white;', '');

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
    if (this._map) {
      this._map.remove();
      this._map = null;
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
    if (this._map) {
      this._map.remove();
      this._map = null;
      this._polyline = null;
    }
    this.shadowRoot.innerHTML = `
      <ha-card header="${this._config.title}">
        <div style="padding: 16px; text-align: center; color: var(--secondary-text-color);">
          No route data available
        </div>
      </ha-card>
    `;
  }

  _renderMap(coordinates, stateObj) {
    const activityName = stateObj.state || 'Activity';

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
        this._map.remove();
        this._map = null;
        this._polyline = null;
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

    if (this._map) {
      this._map.remove();
      this._map = null;
    }

    this._map = L.map(mapContainer, {
      zoomControl: true,
      scrollWheelZoom: false
    });

    // Custom tile layer that sets referrerPolicy BEFORE src so the browser
    // sends no Referer header — required when HA runs on localhost.
    const NoRefererTileLayer = L.TileLayer.extend({
      createTile(coords, done) {
        const tile = document.createElement('img');
        tile.referrerPolicy = 'no-referrer';  // must be before src
        L.DomEvent.on(tile, 'load', L.Util.bind(this._tileOnLoad, this, done, tile));
        L.DomEvent.on(tile, 'error', L.Util.bind(this._tileOnError, this, done, tile));
        tile.alt = '';
        tile.setAttribute('role', 'presentation');
        tile.src = this.getTileUrl(coords);
        return tile;
      }
    });

    new NoRefererTileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(this._map);

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

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'garmin-polyline-card',
  name: 'Garmin Polyline Card',
  description: 'Display Garmin activity routes on a map'
});

console.info('%c GARMIN-POLYLINE-CARD %c loaded ', 'background: #FF5722; color: white;', '');

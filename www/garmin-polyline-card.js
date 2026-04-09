/**
 * Garmin Activity Polyline Map Card
 * A simple custom Lovelace card to display activity routes from sensor attributes
 */

const LEAFLET_VERSION = '1.9.4';
const LEAFLET_JS  = `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.js`;
const LEAFLET_CSS = `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.css`;

// Load Leaflet JS and fetch the CSS text (so it can be injected into shadow roots).
// document.head stylesheets do NOT pierce shadow DOM — only inlined <style> text does.
let _leafletReady = null;
let _leafletCSSText = '';

function loadLeaflet() {
  if (_leafletReady) return _leafletReady;
  _leafletReady = (async () => {
    // Fetch CSS text first — needed before map init
    if (!_leafletCSSText) {
      const resp = await fetch(LEAFLET_CSS);
      _leafletCSSText = await resp.text();
    }
    // Load JS
    if (!window.L) {
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.crossOrigin = 'anonymous';
        script.src = LEAFLET_JS;
        script.onload = resolve;
        script.onerror = () => reject(new Error('Failed to load Leaflet from CDN'));
        document.head.appendChild(script);
      });
    }
  })();
  return _leafletReady;
}


class GarminPolylineCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._config = null;
    this._map = null;
    this._polyline = null;
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

    const stateObj = hass.states[this._config.entity];
    const polylineData = stateObj?.attributes[this._config.attribute];
    const key = polylineData ? JSON.stringify(polylineData) : null;
    if (key === this._lastPolylineKey) return;
    this._lastPolylineKey = key;

    this._updateMap();
  }

  connectedCallback() {
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
      try {
        if (this._polyline) {
          this._polyline.setLatLngs(coordinates);
          this._map.invalidateSize();
          this._map.fitBounds(this._polyline.getBounds(), { padding: [20, 20] });
        }
      } catch (_e) {
        this._map.remove();
        this._map = null;
        this._polyline = null;
        this._renderMap(coordinates, stateObj);
      }
      return;
    }

    // Inject Leaflet CSS as a <style> block so it applies inside the shadow root.
    // A <link> in the shadow root loads async and Leaflet reads dimensions sync on init.
    // _leafletCSSText may be empty on first call; loadLeaflet() fills it before _initMap runs.
    this.shadowRoot.innerHTML = `
      <style>${_leafletCSSText}</style>
      <ha-card header="${this._config.title}">
        <div id="map" style="height: ${this._config.height}; width: 100%;"></div>
        <div style="padding: 8px 16px; font-size: 12px; color: var(--secondary-text-color);">
          ${activityName} • ${coordinates.length} points
        </div>
      </ha-card>
    `;

    loadLeaflet().then(() => {
      // Re-inject CSS now that we have the text (first-call case)
      const style = this.shadowRoot.querySelector('style');
      if (style && !style.textContent) style.textContent = _leafletCSSText;
      this._initMapWhenReady(coordinates);
    }).catch(err => console.error('garmin-polyline-card:', err));
  }

  _initMapWhenReady(coordinates, retries = 0) {
    const MAX_RETRIES = 10;
    requestAnimationFrame(() => {
      const mapContainer = this.shadowRoot.getElementById('map');
      if (!mapContainer) return;

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

    // Set referrerPolicy before src so no Referer header is sent with tile requests
    const NoRefererTileLayer = L.TileLayer.extend({
      createTile(coords, done) {
        const tile = document.createElement('img');
        tile.referrerPolicy = 'no-referrer';
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

    if (coordinates.length > 0) {
      L.circleMarker(coordinates[0], {
        radius: 8, color: '#4CAF50', fillColor: '#4CAF50', fillOpacity: 1
      }).addTo(this._map).bindPopup('Start');

      L.circleMarker(coordinates[coordinates.length - 1], {
        radius: 8, color: '#F44336', fillColor: '#F44336', fillOpacity: 1
      }).addTo(this._map).bindPopup('End');
    }

    this._map.invalidateSize();
    this._map.fitBounds(this._polyline.getBounds(), { padding: [20, 20] });

    setTimeout(() => {
      if (this._map && this._polyline) {
        this._map.invalidateSize();
        this._map.fitBounds(this._polyline.getBounds(), { padding: [20, 20] });
      }
    }, 200);
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

const map = L.map('map', {zoomControl: true}).setView([26.8467, 80.9462], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap contributors',
  maxZoom: 19
}).addTo(map);

let origin = null;
let dest = null;
let markers = [];
let routeLine = null;
let results = [];
let routeKm = 0;
let lastWeather = window.GRWEATHER || {};
let routeDuration = 0;

const csrf = () => document.querySelector('meta[name=csrf-token]').content;
const toast = (message, type='info') => window.showToast ? window.showToast(message, type) : alert(message);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function setBusy(on) {
  const button = document.querySelector('#compare');
  button.disabled = on;
  button.innerHTML = on ? 'Calculating <span class="spinner"></span>' : 'Compare all modes <span>→</span>';
}

function addMarker(point, label, kind='') {
  const marker = L.marker(point).addTo(map).bindPopup(`<b>${esc(label)}</b><br><small>${kind || 'Route point'}</small>`);
  marker.openPopup();
  markers.push(marker);
}

function clearRouteLine() {
  if (routeLine) {
    map.removeLayer(routeLine);
    routeLine = null;
  }
}

map.on('click', e => {
  if (!origin) {
    origin = e.latlng;
    addMarker(e.latlng, 'Origin', 'Map point');
    document.querySelector('#origin').value = `Map point (${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)})`;
  } else if (!dest) {
    dest = e.latlng;
    addMarker(e.latlng, 'Destination', 'Map point');
    document.querySelector('#dest').value = `Map point (${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)})`;
    document.querySelector('#routeMeta').innerHTML = '<b>Both points set.</b><span>Press Compare all modes.</span>';
  } else {
    toast('Both route points are already set. Use Reset route to choose new points.', 'info');
  }
});

async function find(which) {
  const q = document.querySelector('#' + which).value.trim();
  if (!q) return toast('Type a place first.', 'error');
  try {
    const r = await fetch('/api/geocode', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
      body: JSON.stringify({q})
    });
    const d = await r.json();
    if (!r.ok) throw Error(d.error || 'Place search failed');
    const p = {lat: d.lat, lng: d.lon};
    if (which === 'origin') origin = p; else dest = p;
    addMarker(p, d.label, which === 'origin' ? 'Origin' : 'Destination');
    map.setView(p, 14);
    document.querySelector('#routeMeta').innerHTML = `<b>${which === 'origin' ? 'Origin' : 'Destination'} located.</b><span>${esc(d.label)}</span>`;
  } catch (error) {
    toast(error.message, 'error');
  }
}

document.querySelector('#geoO').onclick = () => find('origin');
document.querySelector('#geoD').onclick = () => find('dest');
document.querySelectorAll('.quick').forEach(group => group.querySelectorAll('.chip').forEach(button => {
  button.onclick = () => {
    document.querySelector('#dest').value = button.dataset.place;
    find('dest');
  };
}));

document.querySelector('#resetRoute').onclick = () => {
  origin = null;
  dest = null;
  results = [];
  routeKm = 0;
  routeDuration = 0;
  markers.forEach(marker => map.removeLayer(marker));
  markers = [];
  clearRouteLine();
  document.querySelector('#origin').value = '';
  document.querySelector('#dest').value = '';
  document.querySelector('#routeMeta').textContent = '';
  document.querySelector('#resultSection').classList.add('hidden');
  map.setView([26.8467, 80.9462], 12);
};

document.querySelector('#compare').onclick = async () => {
  if (!origin || !dest) return toast('Set both origin and destination first.', 'error');
  setBusy(true);
  try {
    const headers = {'Content-Type': 'application/json', 'X-CSRFToken': csrf()};
    const rr = await fetch('/api/route', {
      method: 'POST', headers,
      body: JSON.stringify({olat: origin.lat, olon: origin.lng, dlat: dest.lat, dlon: dest.lng})
    });
    const route = await rr.json();
    if (!rr.ok) throw Error(route.error || 'Could not calculate route.');
    routeKm = route.distance_km;
    routeDuration = route.duration_min;
    clearRouteLine();
    if (route.geometry && Array.isArray(route.geometry.coordinates)) {
      const latLngs = route.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
      routeLine = L.polyline(latLngs, {weight: 6, opacity: .85}).addTo(map);
      map.fitBounds(routeLine.getBounds(), {padding: [40, 40]});
    } else {
      const line = [[origin.lat, origin.lng], [dest.lat, dest.lng]];
      routeLine = L.polyline(line, {weight: 5, dashArray: '8 8', opacity: .65}).addTo(map);
      map.fitBounds(routeLine.getBounds(), {padding: [60, 60]});
    }

    const cr = await fetch('/api/compare', {
      method: 'POST', headers,
      body: JSON.stringify({distance_km: routeKm})
    });
    const data = await cr.json();
    if (!cr.ok) throw Error(data.error || 'Could not compare modes.');
    results = data.items || [];
    lastWeather = data.weather || {};
    document.querySelector('#routeMeta').innerHTML = `<b>${route.distance_km} km</b><span>${route.duration_min} min road estimate</span><small>${esc(route.source)}</small>`;
    render(lastWeather);
    document.querySelector('#resultSection').classList.remove('hidden');
    document.querySelector('#resultSection').scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (error) {
    toast(error.message, 'error');
  } finally {
    setBusy(false);
  }
};

document.querySelector('#sort').onchange = () => render(lastWeather);

document.querySelector('#askRouteAI').onclick = () => {
  const sorted = [...results].filter(x => x.feasible).sort((a,b) => b.green_score - a.green_score);
  const base = sorted[0] || results[0];
  const context = {
    message: `Compare this ${routeKm.toFixed(1)} km commute. Consider time, cost, CO₂ and practical weather constraints, then explain the trade-off.`,
    distance_km: routeKm,
    time_hour: new Date().getHours()
  };
  localStorage.setItem('greenroute_ai_context', JSON.stringify(context));
  window.location.href = '/ai';
};

function render(weather) {
  const key = document.querySelector('#sort').value;
  const sorted = [...results].sort((a, b) => key === 'green_score' || key === 'calories' ? b[key] - a[key] : a[key] - b[key]);
  const best = sorted[0];
  if (!best) return;
  document.querySelector('#results').innerHTML = sorted.map((x, i) => `
    <article class="mode-card ${i === 0 ? 'best' : ''} ${x.feasible ? '' : 'unavailable'}">
      <div class="mode-top"><span class="mode-icon">${icon(x.code)}</span><div><b>${esc(x.name)}</b><small>${i === 0 ? 'Highlighted by current sort' : x.feasible ? 'Available candidate' : 'Not practical here'}</small></div><span class="score">${esc(x.green_score)}</span></div>
      <div class="mode-metrics"><div><small>TIME</small><b>${esc(x.time)} min</b></div><div><small>COST</small><b>₹${esc(x.cost)}</b></div><div><small>CO₂</small><b>${esc(x.co2)} kg</b></div><div><small>ACTIVE</small><b>${esc(x.calories)} cal</b></div></div>
      ${x.notes?.length ? `<div class="warning">⚠ ${esc(x.notes[0])}</div>` : ''}
      <div class="scorebar"><i style="width:${Math.max(0, Math.min(100, x.green_score))}%"></i></div>
      <button class="btn ${i === 0 ? 'primary' : ''} full" ${x.feasible ? '' : 'disabled'} onclick="take('${esc(x.code)}')">${x.feasible ? 'Log this trip' : 'Not practical here'} <span>→</span></button>
    </article>`).join('');

  const baselineCo2 = routeKm * 0.18 + 8;
  const baselineCost = routeKm * 8.5 + 8;
  const saved = Math.max(0, baselineCo2 - best.co2);
  const money = Math.max(0, baselineCost - best.cost);
  document.querySelector('#bestSaved').textContent = saved.toFixed(1) + ' kg';
  document.querySelector('#bestMoney').textContent = '₹' + money.toFixed(0);
  document.querySelector('#bestCalories').textContent = Math.round(best.calories);
  document.querySelector('#bestImpact').textContent = (saved * 100 / 1000).toFixed(1) + ' t';
  document.querySelector('#resultSummary').textContent = `${routeKm.toFixed(1)} km route · ${routeDuration.toFixed(0)} min driving estimate · ${weather.label || 'conditions loaded'} · AQI ${weather.aqi ?? '—'}`;
  document.querySelector('#recommendation').innerHTML = `<span class="rec-icon">✦</span><div><b>${esc(best.name)} is highlighted for this view</b><span>${esc(reason(best, weather))} Comparative index: ${esc(best.green_score)}/100. Use Ask AI for a natural-language decision based on your own priorities.</span></div>`;
}

function reason(x, weather) {
  if (!x.feasible) return 'This option is outside the practical-distance rules used by GreenRoute.';
  if (weather.rain > 2 && ['walk','bicycle'].includes(x.code)) return 'Current rain is lowering the practicality of active travel.';
  if (weather.aqi > 120 && ['walk','bicycle'].includes(x.code)) return 'Current AQI is high, so outdoor exposure deserves extra consideration.';
  if (x.code === 'carpool') return 'Sharing the vehicle changes the per-passenger impact and cost.';
  if (['walk','bicycle'].includes(x.code)) return 'This option combines low direct emissions with active travel.';
  return 'This view balances the available time, cost, emissions and activity estimates.';
}

function icon(code) {
  return ({walk:'🚶', bicycle:'🚲', erickshaw:'🛺', bus:'🚌', metro:'🚇', motorbike:'🏍️', auto:'🛺', car:'🚗', carpool:'🚘'})[code] || '🌱';
}

async function take(mode) {
  try {
    const r = await fetch('/api/take-trip', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
      body: JSON.stringify({mode, distance_km: routeKm, origin: document.querySelector('#origin').value || 'Map point', destination: document.querySelector('#dest').value || 'BBDNITM'})
    });
    const d = await r.json();
    if (!r.ok) throw Error(d.error || 'Could not log trip.');
    document.querySelector('#recommendation').innerHTML = `<span class="rec-icon">✓</span><div><b>${esc(d.mode)} logged successfully</b><span>+${esc(d.points)} Green Points · ${esc(d.saved)} kg CO₂ saved · ₹${esc(d.money_saved)} estimated money saved · ${esc(d.streak)}-day streak.</span></div>`;
    toast('Trip logged. Your Impact dashboard has been updated.', 'success');
  } catch (error) {
    toast(error.message, 'error');
  }
}

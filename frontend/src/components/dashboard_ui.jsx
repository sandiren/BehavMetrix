import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, ScatterChart, Scatter, CartesianGrid } from 'recharts';
import ForceGraph2D from 'react-force-graph';

const API = axios.create({
  baseURL: '/api'
});

const BEHAVIOR_OPTIONS = ['grooming', 'aggression', 'self-directed behavior', 'play', 'submission', 'foraging', 'vocalization'];
const REASONS = ['Routine Welfare Check', 'Clinical Follow-up', 'Behavioral Study', 'Environmental Change'];

const FlagBadge = ({ status }) => {
  const colors = {
    green: 'bg-flag-green',
    yellow: 'bg-flag-yellow',
    red: 'bg-flag-red'
  };
  return <span className={`px-2 py-1 rounded-full text-xs text-white ${colors[status] ?? 'bg-slate-400'}`}>{status?.toUpperCase()}</span>;
};

const makeWeightTrend = (animal) => {
  const base = animal.weight ?? 0;
  return [
    { name: 'W-3', value: Math.max(base - 0.6, 0) },
    { name: 'W-2', value: Math.max(base - 0.3, 0) },
    { name: 'Now', value: base }
  ];
};

const AnimalCard = ({ animal }) => (
  <div className="bg-white rounded-xl shadow-sm p-4 flex flex-col gap-2 border border-slate-200">
    <div className="flex justify-between items-start">
      <div>
        <h3 className="text-lg font-semibold">{animal.animalId}</h3>
        <p className="text-xs text-slate-500">Cage {animal.cageId} • {animal.sex}</p>
      </div>
      <FlagBadge status={animal.flag} />
    </div>
    <div className="grid grid-cols-2 gap-2 text-sm">
      <div>
        <p className="text-slate-500">Welfare</p>
        <p className="font-semibold">{animal.welfareScore ?? '—'}</p>
      </div>
      <div>
        <p className="text-slate-500">Rank</p>
        <p className="font-semibold">{animal.socialRank ? animal.socialRank.toFixed(0) : '—'}</p>
      </div>
      <div>
        <p className="text-slate-500">Age</p>
        <p className="font-semibold">{animal.age}</p>
      </div>
      <div>
        <p className="text-slate-500">Weight</p>
        <p className="font-semibold">{animal.weight} kg</p>
      </div>
    </div>
    <div className="h-20">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={makeWeightTrend(animal)}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" hide />
          <YAxis hide domain={['auto', 'auto']} />
          <Tooltip formatter={(value) => `${value.toFixed(1)} kg`} />
          <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
    <div className="text-xs text-slate-500">Enrichment: {animal.enrichmentStatus ?? 'Not logged'}</div>
  </div>
);

const BehaviorLogger = ({ animals, onLogged }) => {
  const [selectedAnimals, setSelectedAnimals] = useState([]);
  const [behavior, setBehavior] = useState(BEHAVIOR_OPTIONS[0]);
  const [reason, setReason] = useState(REASONS[0]);
  const [timestamp, setTimestamp] = useState(() => new Date().toISOString().slice(0, 16));
  const [intensity, setIntensity] = useState(1);

  const toggleAnimal = (id) => {
    setSelectedAnimals((current) =>
      current.includes(id) ? current.filter((animalId) => animalId !== id) : [...current, id]
    );
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!selectedAnimals.length) return;

    const payload = selectedAnimals.map((id) => ({
      animal_id: id,
      behavior,
      intensity,
      reason,
      timestamp: new Date(timestamp).toISOString()
    }));
    await API.post('/behaviors/batch', payload);
    setSelectedAnimals([]);
    onLogged?.();
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-slate-200 p-4 flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Behavior Logging</h2>
        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg shadow"
          disabled={!selectedAnimals.length}
        >
          Log {selectedAnimals.length || ''}
        </button>
      </div>
      <div className="flex gap-4 flex-wrap">
        <label className="flex flex-col text-sm gap-1">
          Behavior
          <select className="border rounded-lg px-3 py-2" value={behavior} onChange={(e) => setBehavior(e.target.value)}>
            {BEHAVIOR_OPTIONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col text-sm gap-1">
          Intensity
          <input
            type="number"
            className="border rounded-lg px-3 py-2"
            min="1"
            max="5"
            value={intensity}
            onChange={(e) => setIntensity(Number(e.target.value))}
          />
        </label>
        <label className="flex flex-col text-sm gap-1">
          Reason for Observation
          <select className="border rounded-lg px-3 py-2" value={reason} onChange={(e) => setReason(e.target.value)}>
            {REASONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col text-sm gap-1">
          Timestamp
          <input
            type="datetime-local"
            className="border rounded-lg px-3 py-2"
            value={timestamp}
            onChange={(e) => setTimestamp(e.target.value)}
          />
        </label>
      </div>
      <div className="flex flex-wrap gap-2">
        {animals.map((animal) => (
          <button
            key={animal.id}
            type="button"
            onClick={() => toggleAnimal(animal.id)}
            className={`px-3 py-2 rounded-full border text-sm ${
              selectedAnimals.includes(animal.id) ? 'bg-blue-600 text-white border-blue-600' : 'border-slate-300 bg-slate-100'
            }`}
          >
            {animal.animalId}
          </button>
        ))}
      </div>
    </form>
  );
};

const SocialHierarchy = ({ animals, interactions, onRefresh }) => {
  const graphData = useMemo(() => {
    const nodes = animals.map((animal) => ({ id: animal.id, name: animal.animalId, val: (animal.socialRank ?? 1000) / 100 }));
    const links = interactions
      .filter((log) => log.actor_id && log.target_id)
      .map((log) => ({
        source: log.actor_id,
        target: log.target_id,
        value: log.behavior === 'aggression' ? 2 : 1
      }));
    return { nodes, links };
  }, [animals, interactions]);

  const handleRecalculate = async () => {
    await API.post('/elo/recalculate');
    onRefresh?.();
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Social Hierarchy</h2>
        <div className="flex gap-2">
          <button className="px-3 py-2 text-sm rounded-lg border" onClick={handleRecalculate}>Recalculate Elo</button>
        </div>
      </div>
      <div className="h-80 border rounded-lg">
        <ForceGraph2D
          graphData={graphData}
          nodeAutoColorBy="id"
          nodeLabel={(node) => `${node.name}`}
          linkColor={() => '#94a3b8'}
        />
      </div>
    </div>
  );
};

const EnrichmentTracker = ({ enrichmentLogs, welfareLookup }) => {
  const correlationData = useMemo(() => {
    return enrichmentLogs.map((log) => ({
      name: log.item,
      welfare: welfareLookup[log.animal_id] ?? 0,
      frequency: log.frequency ?? 1
    }));
  }, [enrichmentLogs, welfareLookup]);

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-col gap-4">
      <h2 className="text-lg font-semibold">Enrichment Tracker</h2>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart>
            <CartesianGrid />
            <XAxis type="number" dataKey="frequency" name="Frequency" />
            <YAxis type="number" dataKey="welfare" name="Welfare Score" />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
            <Scatter name="Items" data={correlationData} fill="#f97316" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
        {enrichmentLogs.slice(0, 8).map((log) => (
          <div key={log.id} className="p-3 rounded-lg border bg-slate-50">
            <p className="font-semibold">{log.item}</p>
            <p className="text-xs text-slate-500">{log.category}</p>
            <p className="text-xs text-slate-500">Duration: {log.duration_minutes ?? '—'} min</p>
            <p className="text-xs text-slate-500">Frequency: {log.frequency ?? '—'}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

const StressMonitor = ({ stressLogs, alerts }) => {
  const latest = stressLogs.slice(0, 12);
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Stress Monitor</h2>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
        {latest.map((log) => (
          <div key={log.id} className="border rounded-lg p-3 bg-slate-50">
            <p className="font-semibold">Animal {log.animal_id}</p>
            <p className="text-xs text-slate-500">{log.indicator}</p>
            <p className="text-xs text-slate-500">Score: {log.value}</p>
            <p className="text-xs text-slate-400">{new Date(log.timestamp).toLocaleString()}</p>
          </div>
        ))}
      </div>
      <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
        <h3 className="font-semibold">Active Alerts</h3>
        <ul className="list-disc ml-5">
          {alerts.length ? alerts.map(([animalId, message]) => (
            <li key={animalId}>Animal {animalId}: {message}</li>
          )) : <li>No alerts</li>}
        </ul>
      </div>
    </div>
  );
};

const DashboardUI = () => {
  const [animals, setAnimals] = useState([]);
  const [behaviorLogs, setBehaviorLogs] = useState([]);
  const [enrichmentLogs, setEnrichmentLogs] = useState([]);
  const [stressLogs, setStressLogs] = useState([]);
  const [alerts, setAlerts] = useState([]);

  const fetchData = async () => {
    const [summaryRes, behaviorRes, enrichmentRes, stressRes, alertRes] = await Promise.all([
      API.get('/dashboard/summary'),
      API.get('/behaviors/recent'),
      API.get('/enrichment'),
      API.get('/stress'),
      API.get('/alerts/stress')
    ]);
    setAnimals(summaryRes.data.animals ?? []);
    setBehaviorLogs(behaviorRes.data ?? []);
    setEnrichmentLogs(enrichmentRes.data ?? []);
    setStressLogs(stressRes.data ?? []);
    setAlerts(alertRes.data.alerts ?? []);
  };

  useEffect(() => {
    fetchData();
  }, []);

  const paddedAnimals = useMemo(() => {
    const copy = [...animals];
    while (copy.length < 80) {
      copy.push({
        id: `placeholder-${copy.length}`,
        animalId: `Unassigned ${copy.length + 1}`,
        cageId: 'TBD',
        sex: '—',
        age: '—',
        weight: 0,
        welfareScore: null,
        socialRank: null,
        enrichmentStatus: 'Pending',
        flag: 'yellow'
      });
    }
    return copy;
  }, [animals]);

  const welfareLookup = useMemo(() => Object.fromEntries(animals.map((animal) => [animal.id, animal.welfareScore ?? 0])), [animals]);

  return (
    <div className="min-h-screen bg-slate-100 p-6 space-y-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold text-slate-800">BehavMetrix Colony Welfare</h1>
        <p className="text-slate-500">Monitoring welfare across outdoor primate colonies with up to 80 macaques.</p>
      </header>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <BehaviorLogger animals={animals} onLogged={fetchData} />
        <SocialHierarchy animals={animals} interactions={behaviorLogs} onRefresh={fetchData} />
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <EnrichmentTracker enrichmentLogs={enrichmentLogs} welfareLookup={welfareLookup} />
        <StressMonitor stressLogs={stressLogs} alerts={alerts} />
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <h2 className="text-lg font-semibold mb-4">Exports & Reports</h2>
          <p className="text-sm text-slate-500 mb-4">Generate exports for individual animals or the entire colony.</p>
          <div className="flex flex-col gap-2">
            <button className="px-4 py-2 rounded-lg bg-slate-800 text-white text-sm" onClick={() => API.get('/exports/animals', { params: { path: 'exports/animals.csv' } })}>Export Animals CSV</button>
            <button className="px-4 py-2 rounded-lg bg-slate-800 text-white text-sm" onClick={() => API.get('/exports/behaviors', { params: { path: 'exports/behaviors.xlsx' } })}>Export Behaviors Excel</button>
            <button className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm" onClick={() => API.get('/exports/weekly-pdf')}>Generate Weekly PDF</button>
          </div>
        </div>
      </section>

      <section className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">Animal Dashboard</h2>
          <span className="text-sm text-slate-500">Displaying {paddedAnimals.length} slots</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {paddedAnimals.map((animal) => (
            <AnimalCard key={animal.id} animal={animal} />
          ))}
        </div>
      </section>
    </div>
  );
};

export default DashboardUI;

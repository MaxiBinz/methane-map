import React from "react";
import { DataComponent, DataTable, ReportSection, RichNarrative, useDataApp } from "../../data-app-public.jsx";
import { FootprintMap } from "./FootprintMap.jsx";
import { reportFigures } from "./figures.js";
import { CandidateMap } from "./CandidateMap.jsx";
import { ScientificFigure } from "./ScientificFigure.jsx";

const previews = {
  "https://doi.org/10.5067/EMIT/EMITL2BCH4ENH.002": { title: "EMIT L2B Methane Enhancement V002", source: "NASA LP DAAC", date: "2025", summary: "The numeric product contains methane enhancement, sensor-noise uncertainty and sensitivity layers, including scenes without cataloged plume complexes.", approvedForReport: true },
  "https://arxiv.org/abs/2604.10094v2": { title: "Global monitoring of methane point sources using deep learning on EMIT radiance", source: "Batchu et al., arXiv v2", date: "2026-07-29", summary: "MAPL-EMIT combines radiance and spatial context for detection, segmentation and source localization. Its reported benchmark results have not been reproduced by this investigation.", approvedForReport: true },
};
const accessColumns = [
  { key: "resource", label: "Resource" }, { key: "state", label: "Observed status" },
  { key: "evidence", label: "Evidence" },
];
const sceneColumns = [
  { key: "observedAt", label: "Observation time (UTC)" },
  { key: "granule", label: "Granule" },
  { key: "role", label: "Frozen role" },
  { key: "cloudPercent", label: "Cloud metadata (%)" },
  { key: "status", label: "Analysis status" },
];
const candidateColumns = [
  { key: "candidate_id", label: "Candidate" }, { key: "category", label: "Evidence" },
  { key: "latitude", label: "Latitude" }, { key: "longitude", label: "Longitude" },
  { key: "peak_ppm_m", label: "Peak (ppm m)" }, { key: "novelty", label: "Novelty assessment" },
];
const metricColumns = [
  { key: "granule", label: "Granule" }, { key: "valid_pixels", label: "Valid pixels" },
  { key: "median_ppm_m", label: "Median (ppm m)" }, { key: "peak_ppm_m", label: "Peak (ppm m)" },
  { key: "candidate_count", label: "Screening components" },
];

export function ReportContent() {
  const { snapshot, visible, canEdit, mode, appTitle, setAppTitle } = useDataApp();
  const [selected, setSelected] = React.useState(null);
  const [selectedCandidate, setSelectedCandidate] = React.useState(null);
  const queries = snapshot.queries ?? {};
  const rows = id => queries[id]?.rows ?? [];
  const story = snapshot.report?.story ?? {};
  const access = rows("access_status");
  const scenes = rows("scene_inventory");
  const candidates = rows("candidates");
  const metrics = rows("scene_metrics");
  const dependencies = {
    summary: ["run_summary", "validation"], results: ["run_summary", "candidates"],
    validation: ["validation", "known_diagnostics"], audit: ["adversarial_audit", "visual_review"], reproducibility: ["reproducibility"], methods: ["run_parameters"],
    limitations: ["run_summary", "adversarial_audit"],
  };
  const narrative = (key, title, queryId) => {
    const queryIds = (dependencies[key] ?? [queryId]).filter(id => queries[id]);
    if (!queryIds.length) queryIds.push(queryId);
    return story[key] && visible(key) && <ReportSection id={key} title={title} queryId={queryIds[0]} queryIds={queryIds}
      sourceRowsByQuery={Object.fromEntries(queryIds.map(id => [id, rows(id)]))} showHeading={false}>
      <RichNarrative id={`${key}:body`} value={story[key]} sourcePreviews={previews} label={`Edit ${title}`} />
    </ReportSection>;
  };

  return <article className="report-content" aria-label="Methane Hunter investigation report">
    <header className="report-hero">
      <h1 data-data-app-title contentEditable={canEdit && mode === "edit"} suppressContentEditableWarning
        onBlur={canEdit && mode === "edit" ? e => setAppTitle(e.currentTarget.textContent.trim() || appTitle) : undefined}
        onKeyDown={canEdit && mode === "edit" ? e => { if(e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); } } : undefined}>{appTitle}</h1>
    </header>
    {narrative("summary", "Executive Summary", queries.run_summary ? "run_summary" : "access_status")}
    {narrative("results", "Observed results", queries.run_summary ? "run_summary" : "access_status")}
    {queries.candidates && candidates.length > 0 && visible("candidate-map") && <DataComponent id="candidate-map" title="What the screening components represent" queryId="candidates" kind="custom" sourceRows={candidates}>
      <CandidateMap rows={candidates} selected={selectedCandidate} onSelect={setSelectedCandidate} />
      <RichNarrative id="candidate-map:caption" value="The map uses actual component polygons and enhancement centroids. E marks a same-acquisition catalog neighborhood; C marks ambiguous evidence. Neither establishes a physical source or independent confirmation. Closely spaced components may overlap; use the selector to inspect every record." label="Edit candidate map caption" />
    </DataComponent>}
    {reportFigures.map(figure => visible(figure.id) && <DataComponent key={figure.id} id={figure.id} title={figure.title} queryId={figure.queryId} kind="custom" sourceRows={rows(figure.queryId).filter(row => !figure.granule || (row.granule ?? row.scene) === figure.granule)}>
      <ScientificFigure figure={figure} />
    </DataComponent>)}
    {scenes.some(row => row.footprintJSON) && visible("region-footprints") && <DataComponent id="region-footprints" title="The bounded region and frozen observation footprints" queryId="scene_inventory" kind="custom" sourceRows={scenes}>
      <FootprintMap rows={scenes} selected={selected} onSelect={setSelected} />
      <RichNarrative id="region-footprints:caption" value="Coordinates show the fixed search box (104.5–102.5° W, 31–33° N) and the frozen sample’s real NASA metadata footprints. Select a footprint or a scene row to inspect it. Footprints do not show cloud-free or scientifically usable coverage." label="Edit map caption" />
    </DataComponent>}
    {narrative("validation", "Validation", queries.validation ? "validation" : "access_status")}
    {queries.validation && visible("validation-table") && <DataComponent id="validation-table" title="Known examples and controls at the frozen baseline" queryId="validation" kind="table" displayRows={rows("validation")} sourceRows={rows("validation")}>
      <DataTable rows={rows("validation")} columns={[{key:"granule",label:"Granule"},{key:"role",label:"Role"},{key:"known_points",label:"Known heads"},{key:"recovered_points",label:"Heads associated"},{key:"components",label:"Components"},{key:"usable_pixels",label:"Usable pixels"}]} searchable={false} caption="Known-positive and catalog-negative-control outcomes" rowKey="granule" />
    </DataComponent>}
    {queries.known_diagnostics && visible("diagnostic-table") && <DataComponent id="diagnostic-table" title="Fixed diagnostics reveal threshold sensitivity" queryId="known_diagnostics" kind="table" displayRows={rows("known_diagnostics")} sourceRows={rows("known_diagnostics")}>
      <DataTable rows={rows("known_diagnostics")} columns={[{key:"scene",label:"Positive scene"},{key:"sigma",label:"Multiplier"},{key:"cm_heads_associated_300m",label:"CM heads associated"},{key:"cm_heads_total",label:"CM heads total"},{key:"nasa_outlines_intersected",label:"NASA outlines intersected"},{key:"nasa_outlines_total",label:"NASA outlines available"}]} searchable={false} caption="Prespecified 3, 5, 7 threshold diagnostics; five remains the baseline" rowKey="id" />
    </DataComponent>}
    {narrative("audit", "Adversarial component review", "adversarial_audit")}
    {queries.adversarial_audit && visible("audit-table") && <DataComponent id="audit-table" title="Initial assessment after adversarial review" queryId="adversarial_audit" kind="table" displayRows={rows("adversarial_audit")} sourceRows={rows("adversarial_audit")}>
      <DataTable rows={rows("adversarial_audit")} columns={[{key:"candidate_id",label:"Component"},{key:"category",label:"Evidence"},{key:"review_priority",label:"Review priority"},{key:"review_flags",label:"Review flags"},{key:"visual_note",label:"Visual inspection note"}]} caption="All fourteen component audit records; no physical independent confirmation" rowKey="candidate_id" />
    </DataComponent>}
    {queries.candidates && visible("candidate-register") && <DataComponent id="candidate-register" title="Candidate evidence register" queryId="candidates" kind="table" displayRows={candidates} sourceRows={candidates}>
      <DataTable rows={candidates} columns={candidateColumns} caption="Candidate findings and initial evidence categories" rowKey="candidate_id" selectedRowKey={selectedCandidate} onRowSelect={row => setSelectedCandidate(row.candidate_id)} rowActionLabel={row => `Inspect ${row.candidate_id}`} />
      {candidates.length === 0 && <RichNarrative id="candidate-register:empty" value={story.candidateEmpty ?? "No candidate rows are recorded. Interpret this only with the stated analysis coverage and validation outcome."} label="Edit candidate status" />}
    </DataComponent>}
    {metrics.length > 0 && visible("scene-measurements") && <DataComponent id="scene-measurements" title="Measurements in the analyzed sample" queryId="scene_metrics" kind="table" displayRows={metrics} sourceRows={metrics}>
      <DataTable rows={metrics} columns={metricColumns} caption="Per-scene numeric measurement summary" rowKey="granule" />
    </DataComponent>}
    {narrative("access", "Access evidence", "access_status")}
    {visible("access-evidence") && <DataComponent id="access-evidence" title="Observed access and runtime checks" queryId="access_status" kind="table" displayRows={access} sourceRows={access}>
      <DataTable rows={access} columns={accessColumns} caption="Data access outcomes" searchable={false} rowKey="resource" />
    </DataComponent>}
    {visible("scene-inventory") && <DataComponent id="scene-inventory" title="Frozen observation records" queryId="scene_inventory" kind="table" displayRows={scenes} sourceRows={scenes}>
      <DataTable rows={scenes} columns={sceneColumns} caption="Frozen NASA CMR metadata records" rowKey="granule" selectedRowKey={selected} onRowSelect={row => setSelected(row.granule)} rowActionLabel={row => `Highlight footprint for ${row.granule}`} />
    </DataComponent>}
    {narrative("methods", "Methods", queries.run_summary ? "run_summary" : "access_status")}
    {narrative("limitations", "Limitations and next evidence", queries.run_summary ? "run_summary" : "access_status")}
    {narrative("reproducibility", "Computational reproducibility", "reproducibility")}
  </article>;
}

"""Rebuild reviewed report evidence from completed local analysis outputs.

No network or scientific calculations are rerun here. This helper preserves the
app identity and presentation source, checks count reconciliation, copies real
figures, and writes an artifact-local reviewed snapshot. Build separately.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
APP = ROOT / 'report_app'

def read(name):
    return json.loads((ROOT / name).read_text())

def digest(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()

def source(label, paths, definitions=(), caveats=()):
    return {
        'label': label, 'provider': 'NASA EMIT / local reproducible analysis; catalog data by Carbon Mapper',
        'executedAt': read('outputs/run_summary.json')['finished_at'],
        'files': paths,
        'filters': ['Frozen region: -104.5,31,-102.5,33', 'Fixed observation sample: 2023-12-24 through 2025-09-22'],
        'caveats': list(caveats), 'metricDefinitions': list(definitions),
        'evidenceFlow': [
            {'title': 'Exact retained inputs', 'detail': '\n'.join(f'{p}\nSHA-256:{digest(p)}' for p in paths)},
            {'title': 'Executed analysis', 'detail': 'Frozen V002 enhancement / sensitivity, supplied uncertainty unchanged; exact GLT quality mapping; baseline local-background and sensor-noise screening. Results are local observed retrieval statistics, not independent gas verification.'},
        ],
    }

def query(rows, label, paths, definitions=(), caveats=(), payload=()):
    q = {'rows': rows, 'source': source(label, paths, definitions, caveats),
         'methods': [{'language': 'text', 'code': 'Read the listed completed JSON output files. Preserve numeric values and nulls. Flatten nested fields only for presentation; source files and hashes retain complete evidence. No observations are synthesized and no source system is modified.'}]}
    if payload:q['payloadColumns']=list(payload)
    return q

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--complete',action='store_true');args=parser.parse_args()
    summary=read('outputs/run_summary.json');scenes=read('outputs/scene_metrics.json');candidates=read('outputs/candidates.json')
    validation=read('outputs/validation.json');diagnostics=read('outputs/known_diagnostics.json');params=read('outputs/run_parameters.json')
    selection=read('data/metadata/nasa_selection.json')
    if summary['provisional'] or summary['scenes_analyzed']!=20 or len(scenes)!=20:
        raise ValueError('Final report requires a completed nonprovisional20-scene run')
    if {s['granule'] for s in scenes}!={s['name'] for s in selection['scenes']}:
        raise ValueError('Analyzed scene population differs from frozen selection')
    counts=Counter(c['category'] for c in candidates)
    assert len(candidates)==summary['screened_components']==sum(s['candidate_count'] for s in scenes)
    assert counts['E']==summary['category_E'] and counts['C']==summary['category_C']
    assert sum(s['valid_pixels'] for s in scenes)==summary['usable_pixel_observations']
    audit=read('outputs/adversarial_audit.json');visual=read('outputs/visual_review.json')
    assert audit['summary']['components_audited']==len(candidates)
    assert {c['candidate_id'] for c in audit['candidates']}=={c['candidate_id'] for c in candidates}
    assert {c['candidate_id'] for c in visual['records']}=={c['candidate_id'] for c in candidates}
    audit_by_id={r['candidate_id']:r for r in audit['candidates']}
    visual_by_id={r['candidate_id']:r for r in visual['records']}
    data=json.loads((APP/'src/data.json').read_text());data['title']='The methane screen ran, but missed known observations'
    data['generatedAt']=datetime.now(timezone.utc).isoformat();data['buildStatus']='complete' if args.complete else 'creating'
    data['status']='reviewed';data['report']['asOf']='2026-10-19'
    evidence=data['queries']
    run_row={k:v for k,v in summary.items() if not isinstance(v,(dict,list))}
    run_row.update({f'{r}_scenes':n for r,n in summary['roles'].items()})
    evidence['run_summary']=query([run_row],'Final twenty-scene execution summary',['outputs/run_summary.json','outputs/run_parameters.json'],[
        {'label':'Usable pixel-observations','definition':'Sum of per-scene quality/sensitivity/uncertainty-eligible pixels inside the ROI; repeated geography and dates are retained. This is not unique area or statistically independent sample size.','componentIds':['summary','results']},
        {'label':'Screening components','definition':'Eight-connected groups of at least four threshold-passing pixels. They may fragment a plume and are not unique sources.','componentIds':['summary','results','limitations']},
        {'label':'Known-example recovery gate','definition':'At least one documented-neighborhood association in each of two positive scenes was required; only one scene had an association, so the gate was not met.','componentIds':['summary','validation','limitations']},
    ],['No A/B evidence categories, emission rates, facility attribution or novelty were established.'])
    metric_rows=[{k:v for k,v in s.items() if not isinstance(v,(dict,list))} for s in scenes]
    evidence['scene_metrics']=query(metric_rows,'Completed per-scene retrieval and screen metrics',['outputs/scene_metrics.json','outputs/run_parameters.json'],[
        {'label':'Corrected enhancement','definition':'NASA CH4ENH divided by unitless CH4SENS, in ppm m; a concentration-path-length enhancement, not an emission rate.','componentIds':['scene-measurements','figure-positive-first','figure-positive-second','figure-control','figure-search']},
        {'label':'Quality-retained fraction','definition':'Usable pixels divided by finite enhancement pixels inside the ROI. Includes quality, sensitivity and uncertainty screening.','componentIds':['scene-measurements']},
    ],['Per-scene maxima are retrieval values and can include unverified artifacts.','All twenty quality mappings passed exact GLT and integer grid checks; this does not validate gas interpretation.'])
    candidate_rows=[]
    for c in candidates:
        row={k:v for k,v in c.items() if not isinstance(v,(dict,list,tuple))}
        row.update(geometryJSON=json.dumps(c['geometry'],separators=(',',':')),catalogMatchesJSON=json.dumps(c['catalog_matches'],separators=(',',':')),flagsText='; '.join(c['flags']),uncheckedText='; '.join(c['unchecked']))
        a=audit_by_id[c['candidate_id']]
        row.update(review_priority=a['review_priority'],auditFlagsText='; '.join(a['review_flags']),
                   visualNote=visual_by_id[c['candidate_id']]['visual_note'],
                   qualityExcludedComponentPixels=a['quality_exclusion_context']['excluded_component_pixels'],
                   nearestExcludedQualityPixel_m=a['quality_exclusion_context']['nearest_excluded_quality_pixel_center_distance_m_within_1500m'])
        candidate_rows.append(row)
    evidence['candidates']=query(candidate_rows,'All baseline component measurements and initial assessments',['outputs/candidates.json','outputs/run_parameters.json','outputs/adversarial_audit.json','outputs/visual_review.json'],[
        {'label':'Evidence E','definition':'Source-point-to-component-polygon distance<=300m in EPSG:32613 and acquisition difference<=120seconds in the saved Carbon Mapper catalog. Empirical neighborhood association, not independent confirmation or exact source identity.','componentIds':['candidate-map','candidate-register','results']},
        {'label':'Evidence C','definition':'An unmatched enhancement remains ambiguous because independent spectra, surface context, winds and another sensor have not established methane/source interpretation.','componentIds':['candidate-map','candidate-register','results']},
        {'label':'Map coordinates','definition':'Enhancement-support geometric centroid in WGS84, not an inferred methane source or facility. Polygons are measured threshold-passing support.','componentIds':['candidate-map','candidate-register']},
        {'label':'Peak enhancement','definition':'Maximum sensitivity-corrected retrieval within the component, in ppm m; not ambient methane or emission rate.','componentIds':['candidate-map','candidate-register']},
    ],['Six E components and eight C components do not establish fourteen unique plumes.','All eight C rows originate in the second positive-validation scene.','Carbon Mapper catalog data are subject to noncommercial attribution/share-alike terms: https://carbonmapper.org/terms.'],payload=['geometryJSON','catalogMatchesJSON'])
    validation_rows=[]
    for v in validation:
        row={k:w for k,w in v.items() if not isinstance(w,(dict,list))}
        row['reference_head_usable']=sum(h['source_head_pixel_usable'] for h in v.get('reference_head_quality',[]))
        row['reference_head_total']=len(v.get('reference_head_quality',[]))
        validation_rows.append(row)
    evidence['validation']=query(validation_rows,'Known-positive and catalog-negative-control outcomes',['outputs/validation.json','outputs/scene_metrics.json'],[
        {'label':'Known heads associated','definition':'Number of saved in-ROI catalog heads with a retained component within300m and120seconds. All in-ROI heads remain in the denominator; masked source-head pixels are disclosed separately.','componentIds':['validation','validation-table','summary']},
        {'label':'Controls','definition':'Two scenes with zero published plumes in the saved provider scene metadata; not guaranteed methane-free truth.','componentIds':['validation','validation-table']},
    ],['One of two positive scenes had a baseline association; the planned gate was not met.','Zero control components does not calibrate a false-positive rate.'])
    diagnostic_rows=[dict(r,id=f'{r["scene"]}:{r["sigma"]}') for r in diagnostics['summary']]
    evidence['known_diagnostics']=query(diagnostic_rows,'Fixed known-example threshold diagnostics',['outputs/known_diagnostics.json'],[
        {'label':'Threshold multiplier','definition':'Prespecified 3, 5, 7 multipliers applied to local robust scatter and supplied sensor noise while preserving the 500 ppm m floor and four-pixel minimum. Baseline 5 was not retuned.','componentIds':['validation','diagnostic-table','figure-positive-first']},
        {'label':'NASA outlines','definition':'Exact-start-time NASA CMR plume-complex outlines for the two known scenes. The second returned none; this is missing query coverage, not a methane-free observation.','componentIds':['validation','diagnostic-table','figure-positive-first']},
    ],diagnostics['limitations'])
    audit_rows=[]
    for a in audit['candidates']:
        audit_rows.append({'candidate_id':a['candidate_id'],'category':a['category_after_audit'],
            'review_priority':a['review_priority'],'contract_checks_passed':a['contract_checks_passed'],
            'review_flags':'; '.join(a['review_flags']),
            'quality_excluded_component_pixels':a['quality_exclusion_context']['excluded_component_pixels'],
            'nearest_excluded_quality_pixel_m':a['quality_exclusion_context']['nearest_excluded_quality_pixel_center_distance_m_within_1500m'],
            'nearby_same_event_catalog_sources':len(a['same_acquisition_catalog_context_within_1km']),
            'annulus_contrast_sigma':a['local_annulus']['contrast_sigma'],
            'independent_corroboration':a['independent_corroboration'],
            'visual_note':visual_by_id[a['candidate_id']]['visual_note']})
    evidence['adversarial_audit']=query(audit_rows,'All-component structural and adversarial review',['outputs/adversarial_audit.json','outputs/visual_review.json'],[
        {'label':'Contract checks','definition':'Time, ROI geometry, source-manifest/ledger metadata and processing consistency checks; these are not independent spectral or atmospheric validation.','componentIds':['audit','audit-table','limitations']},
        {'label':'Quality proximity','definition':'UTM component-polygon to nearest excluded quality-pixel center within1500m, approximate at half-pixel scale. Proximity is context, not proof of contamination; no component contains excluded pixels.','componentIds':['audit','audit-table','candidate-map']},
    ],['All14 initial categories remain6E/8C.','Two pairs may be threshold fragments of one feature; no automatic source-count merge was made.','No physical independent validation or novelty was established.'])
    evidence['visual_review']=query(visual['records'],'Visual inspection notes for every numeric-data component panel',['outputs/visual_review.json','outputs/maps/component_review.json'],caveats=['Assistant visual inspection of all fourteen panels; no independent radiance, wind, surface or sensor validation.','No category changes.'])
    parameter_rows=[{'parameter':k,'value':v} for k,v in params['config'].items()]
    parameter_rows += [{'parameter':'catalog_polygon_distance_m','value':300},{'parameter':'catalog_time_seconds','value':120}]
    evidence['run_parameters']=query(parameter_rows,'Frozen baseline processing parameters',['outputs/run_parameters.json','data/metadata/nasa_selection.json'],[
        {'label':'Sensor uncertainty convention','definition':'Use the delivered sensitivity-corrected UNCERT unchanged; dividing it by SENS again would double-correct.','componentIds':['methods']},
    ],['The screen is an uncalibrated hypothesis generator.'])
    replay=read('outputs/reproducibility.json')
    suite=ET.parse(ROOT/'outputs/test_results.xml').getroot().find('testsuite')
    if suite is None:raise ValueError('Missing pytest suite receipt')
    receipt={'scenes_replayed':replay['scenes'],'components_compared':replay['components'],
             'comparison':replay['comparison'],'replay_status':replay['status'],
             'tests':int(suite.attrib['tests']),'failures':int(suite.attrib['failures']),
             'errors':int(suite.attrib['errors']),'skipped':int(suite.attrib['skipped'])}
    evidence['reproducibility']=query([receipt],'Exact replay and essential software test receipts',['outputs/reproducibility.json','outputs/test_results.xml'],[
      {'label':'Replay equality','definition':'Exact equality of all twenty scene-metric records and the compared numeric, geometric and category fields for fourteen components, with identical inputs and implementation.','componentIds':['reproducibility']},
      {'label':'Essential tests','definition':'Counts from the recorded pytest XML suite; software tests do not constitute independent methane validation.','componentIds':['reproducibility']},
    ],['One-implementation replay establishes computational repeatability, not independent physical confirmation.'])
    # Reconcile actual frozen scene metadata with completed execution status.
    by_name={s['granule']:s for s in scenes}
    for row in evidence['scene_inventory']['rows']:
        measured=by_name[row['granule']]
        row['status']=f'Analyzed; {measured["candidate_count"]} components; quality grid passed'
    evidence['scene_inventory']['source']['caveats']=['Frozen convenience sample; footprints show metadata coverage, not valid area.','All twenty selected scenes were analyzed; use scene_metrics for actual usable support.','NASA and Carbon Mapper cloud estimates differ; NASA CMR percentages are shown.']
    evidence['scene_inventory']['source']['files']=['data/metadata/nasa_selection.json','outputs/scene_metrics.json']
    evidence['access_status']['rows']=[
        {'resource':'NASA numeric input acquisition','state':'Completed','evidence':'20 frozen scenes with enhancement, sensitivity, uncertainty and matching official MASK inputs','scientific_use':'Actual full-scene numeric processing'},
        {'resource':'Quality-grid verification','state':'20 passed','evidence':'Exact one-based GLT and integer window correspondence','scientific_use':'Processing alignment check; not gas truth'},
        {'resource':'Known-positive recovery','state':'Gate not met','evidence':'Only1of2 known-positive scenes had a baseline catalog-neighborhood association','scientific_use':'Insufficient basis for strong discovery claims'},
        {'resource':'Independent corroboration','state':'Unavailable','evidence':'No second sensor, independent spectral fit, wind or facility verification','scientific_use':'No newly corroborated source or emission rate'},
    ]
    evidence['access_status']['source']=source('Completed acquisition and validation status',['data/nasa_input_manifest.json','outputs/run_summary.json','outputs/validation.json'])
    csearch=[c for c in candidates if c['role']=='search'];controls=[v for v in validation if v['role']=='control_validation']
    control_pixels=sum(v['usable_pixels'] for v in controls)
    data['report']['story']={
        'summary':f'''## Executive Summary\n\nThe pipeline analyzed **20 real NASA EMIT granules**, but its baseline did not pass the planned known-example recovery gate: only **1 of 2 positive scenes** had a documented-observation association. No independently corroborated new methane source was established.\n\n- The16search granules produced **{len(csearch)}components**, all associated with published same-acquisition neighborhoods.\n- Across every role, **14components** received initial assessments: **6E(documented neighborhood)** and **8C(ambiguous)**. All eightC components came from the23March2025 positive-validation scene. Components are not unique physical plumes or sources.\n- The two catalog-negative controls produced zero baseline components over{control_pixels:,}usable pixel-observations; they are not guaranteed methane-free truth.\n\nThe main finding is a sensitivity limitation, together with a reproducible bounded search—not a regional completeness result.''',
        'results':f'''## Four search responses were already documented\n\nThe frozen sample spans **{summary['distinct_dates']}dates**, from24December2023 to22September2025, inside the northern Delaware Basin search box. The completed pipeline processed **15.9Musable pixel-observations**. This count retains repeated geography and is neither unique area nor15.9Mindependent measurements.\n\nThe four baseline search components were all categoryE. Eight ambiguous components also remained in a known-positive scene. Their strong retrieval values warrant scrutiny, but existing spectral, surface, cloud or noise explanations have not been independently ruled out. Each component has a numeric dossier and a separate novelty assessment.''',
        'validation':'''## The strict baseline missed known observations\n\nOn23August2024 the baseline retained no components around four cataloged source heads. On23March2025 it associated components with **1of10heads** at300m. Two retained components associated with the same head, so component count cannot be equated with source count. Two of the first scene's four source-head pixels were quality-excluded; all ten in the second were usable. Downwind plume geometry can differ from head-pixel quality.\n\nThe prespecified three-times diagnostic associated **2of4heads** in the first scene and **7of10** in the second; the seven-times diagnostic recovered none. In the first scene, three-times components intersected **2of3NASA outlines**. The second exact-start-time NASA outline query returned none, which is a coverage limitation. The baseline remained five-times throughout.\n\nCloud-buffer exclusions, the sensor-noise threshold and the minimum connected support explain parts of the misses. These checks reuse the same retrievals and catalogs. They do not independently confirm methane or validate unmatched components.''',
        'access':'''## The numeric investigation ran on full scenes\n\nUser-authorized Earthdata access resolved the initial anonymous download failure. All twenty frozen scenes were processed with V002 enhancement, sensitivity and uncertainty plus matching official quality data. Public catalog-selected plume crops were kept separate and were not used as neutral background or negative controls.\n\nThe input manifest retains source identifiers, URLs, content hashes and byte counts. Credentials are absent from the report and project artifacts.''',
        'methods':'''## How the screen generated hypotheses\n\nCorrected enhancement equals NASA CH4ENH divided by CH4SENS, in **ppm m**. Supplied UNCERT remains unchanged; NASA's actual processing expression already normalizes it for sensitivity. Official Cloud, Cirrus, Water, Spacecraft and Dilated Cloud flags were mapped by exact GLT correspondence. All20grid checks passed. Passing masks does not establish true gas.\n\nThe frozen screen required at least four8-connected pixels above **max(500ppm m,local background+5robust sigma,local background+5sensor uncertainty)**, with sensitivity>0.1. Local robust statistics used128-pixel tiles. There was no smoothing or mask growth.\n\nCatalog matching measured source-point-to-component-polygon distance in EPSG:32613, with empirical **300m/120second** tolerances. The same photons underlie the catalog comparison, so agreement is documentation rather than independent corroboration. [NASA V002](https://doi.org/10.5067/EMIT/EMITL2BCH4ENH.002) and [MAPL-EMIT](https://arxiv.org/abs/2604.10094v2) provide the scientific context; MAPL inference was not run here.''',
        'limitations':'''## What remains uncertain\n\nThis provider-influenced convenience sample cannot establish regional catalog completeness. The failed positive gate makes the absence of novel search candidates especially uninformative about weaker emissions. A finite catalog, empirical matching tolerance and region boundary can all leave a previously documented feature unmatched.\n\nAll eight categoryC responses remain ambiguous. The next useful check is an independent radiance/surface-context review, followed where possible by another sensor or near-coincident observation. No independent wind field, facility attribution, emission rate or annualization was produced. Re-thresholding is a robustness experiment, not independent evidence.''',
    }
    data['report']['story']['audit']='''## Every component received a skeptical review\n\nAll **14** components passed the separate structural/provenance consistency checks, and all14 numeric-data map panels were visually inspected. These checks do not establish atmospheric methane. Categories remained **6E/8C**, with no A or B findings.\n\nTwo component pairs may be fragments of the same visible feature. Two C components lie300–1000m from a same-acquisition catalog source; one also has weak local-annulus contrast. Six components lie within1.5km of excluded-quality pixel centers, although no retained component contains excluded pixels. Proximity alone does not prove contamination.\n\nThe visual review found compact unresolved clusters and several elongated or fragmented features. No independent spectral fit, surface comparison, wind or another sensor resolved the alternatives. No repeated component neighborhood across dates was found in this sample; that absence does not establish transience or novelty.'''
    data['report']['story']['reproducibility']=f'''## The computation reproduced exactly\n\nA complete local replay reproduced **{receipt['scenes_replayed']}scene-metric records** and the compared numeric, geometric and category fields for **{receipt['components_compared']}components** exactly. The recorded essential suite passed **{receipt['tests']}tests**, with {receipt['failures']}failures, {receipt['errors']}errors and {receipt['skipped']}skips.\n\nThese are software and reproducibility checks. Repeating one implementation on identical observations does not provide independent methane confirmation.'''
    replacements={'The16search':'The 16 search','4components':'4 components','14components':'14 components','6E(':'6 E (','8C(':'8 C (','eightC':'eight C','the23March2025':'the 23 March 2025','over572,084usable':'over 572,084 usable','16dates':'16 dates','from24December2023':'from 24 December 2023','to22September2025':'to 22 September 2025','15.9Musable':'15.9M usable','nor15.9Mindependent':'nor 15.9M independent','categoryE':'category E','categoryC':'Category C','sigma,local':'sigma, local','On23August2024':'On 23 August 2024','On23March2025':'On 23 March 2025','1of10heads':'1 of 10 heads','at300m':'at 300 m','2of4heads':'2 of 4 heads','7of10':'7 of 10','2of3NASA':'2 of 3 NASA','All20grid':'All 20 grid','four8-connected':'four 8-connected','500ppm':'500 ppm','m,local':'m, local','background+5robust':'background + 5 robust','background+5sensor':'background + 5 sensor','used128':'used 128','300m/120second':'300 m / 120-second','all14':'all 14','6E/8C':'6 E / 8 C','lie300–1000m':'lie 300–1000 m','within1.5km':'within 1.5 km','20scene-metric':'20 scene-metric','14components':'14 components','56tests':'56 tests','0failures':'0 failures','0errors':'0 errors','0skips':'0 skips'}
    for key,text in data['report']['story'].items():
        for old,new in replacements.items():text=text.replace(old,new)
        data['report']['story'][key]=text
    assets=APP/'src/content/assets';assets.mkdir(exist_ok=True)
    figures=[];imports=[]
    specs=[
      ('outputs/maps/validation_thresholds.png','validation_thresholds.png','figure-positive-first','The first known scene responds at three-times, but misses at baseline five-times','known_diagnostics',scenes[0]['granule'],'Fixed threshold diagnostics for the first positive scene. Both panels use actual retrieved enhancement and the same scientific observation; re-thresholding is not independent evidence.'),
      ('outputs/maps/scene_02.png','scene_02.png','figure-positive-second','The second positive scene contains ten screening components','scene_metrics',scenes[1]['granule'],'23 March 2025: ten baseline components, including all eight ambiguous C responses. Colors are corrected retrievals in ppm m; gray means unavailable or quality-excluded. Coordinates describe enhancement context rather than a facility.'),
      ('outputs/maps/scene_09.png','scene_09.png','figure-search','A search response reproduces an existing observation neighborhood','scene_metrics',scenes[8]['granule'],'12 February 2024: one baseline component associated with a published observation. This is same-observation documentation rather than independent corroboration. The color scale is sensitivity-corrected ppm m.'),
      ('outputs/maps/component_review.png','component_review.png','figure-component-review','All fourteen components retain unresolved physical alternatives','candidates',None,'Actual numeric-data close-ups for every baseline component. All panels were visually inspected; the visual review made no category changes. E denotes a published-observation neighborhood and C ambiguous evidence. Visual morphology alone does not establish a source, facility or rate.'),
    ]
    for index,(path,name,identity,title,qid,granule,caption) in enumerate(specs):
        shutil.copy2(ROOT/path,assets/name);alias=f'image{index}'
        imports.append(f'import {alias} from "../assets/{name}";')
        figures.append({'id':identity,'title':title,'src':alias,'granule':granule,'queryId':qid,
            'alt':title+'; actual scientific map with units and selection annotations retained.', 'caption':caption})
    text='\n'.join(imports)+'\nexport const reportFigures = [\n'
    for f in figures:
        alias=f.pop('src');parts=[f'{json.dumps(k)}:{json.dumps(v)}' for k,v in f.items()];parts.append(f'"src":{alias}');text+='  {'+','.join(parts)+'},\n'
    (APP/'src/content/report/figures.js').write_text(text+'];\n')
    (APP/'src/data.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'scenes':len(scenes),'candidates':len(candidates),'categories':counts,'buildStatus':data['buildStatus']}))

if __name__=='__main__':main()

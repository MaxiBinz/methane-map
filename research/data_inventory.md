# Data inventory and selection audit

Audit date: 19 October 2026 (Europe/Vienna). Source metadata snapshots were retrieved on 18 October 2026 UTC; embedded retrieval times are authoritative. Raw-file acquisition is tracked separately and may continue after this inventory was written. This document audits the frozen selection; it does not assert that every selected file has finished downloading or passed pixel-quality validation.

## Actual sources and intended uses

| Source | Version / interface | Role in this investigation | Local provenance |
|---|---|---|---|
| NASA EMIT methane enhancement | EMITL2BCH4ENH V002, DOI [10.5067/EMIT/EMITL2BCH4ENH.002](https://doi.org/10.5067/EMIT/EMITL2BCH4ENH.002); public CMR discovery, authenticated LP DAAC scientific downloads | Full-scene enhancement, noise uncertainty, sensitivity; separate units and correction conventions apply | `data/metadata/nasa_selection.json`, `nasa_matched_cmr.json`, `cmr_enh_collection.json`; `data/nasa_download_ledger.json` records acquired files |
| NASA EMIT quality masks | EMITL2ARFL V001, [10.5067/EMIT/EMITL2ARFL.001](https://doi.org/10.5067/EMIT/EMITL2ARFL.001), MASK files within RFL granules | Cloud, cirrus, water and other quality context; native sensor grid requires documented GLT mapping | Each selected record preserves the matching RFL CMR granule and quality URL |
| Carbon Mapper | [Catalog API](https://api.carbonmapper.org/api/v1/docs), EMIT instrument (`emi`) and methane (`CH4`) filters | Published source-location reference and public-scene selection metadata | `data/metadata/carbonmapper_selection.json`, `carbonmapper_regional_plumes.json`, `carbonmapper_stac.json` |
| NASA U.S. Greenhouse Gas Center | [EMIT plume collection](https://earth.gov/eic/api/stac/ghgc/collections/emit-ch4plume-v2), EMITL2BCH4PLM V002 scientific raster export | Supplementary known-product checks during initial authentication investigation; plume-selected support is unsuitable for an unbiased scene search | `data/metadata/public_crop_stac.json`, `public_crop_selection.json`; `data/public_download_ledger.json` |
| Google Research MAPL | [Repository](https://github.com/google-research/mapl), inspected documentation | Prior-method review; no MAPL model inference or pretrained-weight validation was performed | Literature review and methodology |

NASA CMR discovery returned all three scientific enhancement-product URLs and an exactly matching L2A MASK URL for each of the 20 scenes. Historical CMR records sometimes use `title` rather than `producer_granule_id`; the frozen manifest preserves the original response and resolved identifier. Metadata matching used a CMR time window of plus/minus one second followed by an exact acquisition-start comparison, not a nearest-scene guess.

The full-scene package is estimated by CMR metadata at approximately **831.9 MB** for the three methane files; that estimate excludes the quality-mask files and is not a measurement of bytes transferred. The download ledgers and actual file sizes govern the 5 GB cap. Metadata requests, failed authentication checks, and the supplementary public crops must also remain visible in the audit trail.

## Licensing and access

NASA-led mission data default to CC0 under the [NASA Science Data Portal policy](https://science.data.nasa.gov/about/license), unless individual data restrictions state otherwise. The GHGC plume collection declares `CC0-1.0`. Product DOI, provider, instrument, versions and granule IDs remain recorded. An open data license does not eliminate Earthdata authentication requirements.

**Source: Carbon Mapper (data.carbonmapper.org).** Its [terms, updated 13 January 2026](https://carbonmapper.org/terms), require purpose-aligned non-commercial use, attribution and corresponding terms for redistribution of data or derived products. Carbon Mapper STAC metadata declares `proprietary`; it must not be relabeled CC0 or Apache-2.0. The local scientific investigation uses the catalog for comparison. Nothing has been publicly deployed or published. MAPL code is Apache-2.0; that code license does not license third-party inputs or imply available pretrained weights.

Anonymous Carbon Mapper full-scene scalar asset requests returned HTTP 401 even though their metadata was readable. Public signed concentration crops and NASA GHGC scientific plume exports were accessible. NASA protected full-scene access was subsequently handled through authorized Earthdata authentication by the primary process. This inventory contains no credential material. Signed ephemeral URL parameters were removed from saved Carbon Mapper metadata.

## Frozen sample and independent checks

Region: **longitude -104.5 to -102.5; latitude 31 to 33**, in the Permian Basin. All analysis must clip to this region. Catalog context can extend beyond it without expanding the analysis region.

The frozen NASA selection contains **20 distinct ENH V002 granule IDs and acquisition timestamps**, with **two positive-validation scenes, two control-validation scenes and 16 search scenes**. All 20 methane and quality-granule start times exactly match their Carbon Mapper scene timestamp. The two positive scenes contain respectively **4 and 10 published methane source points inside both the fixed region and the actual CMR scene polygon**. Both control scenes have zero published plumes in the selected Carbon Mapper scene metadata; this is a catalog-based label, not proof of a methane-free atmosphere.

The sample derives from publicly listed Carbon Mapper scenes with its cloud-cover estimate at most 25%, then reserves validation roles within the fixed 20 scenes. It is **not a random or exhaustive sample of NASA EMIT coverage**. NASA cloud estimates differ substantially and are retained separately; neither provider's scene-level percentage substitutes for a pixel mask.

| NASA granule | Role | CM CH4 points in region | Cloud % CM / NASA | Native footprint intersecting region, km² |
|---|---|---:|---:|---:|
| `EMIT_L2B_CH4ENH_002_20240823T173410_2423611_025` | positive_validation | 4 | 25 / 20 | 6,283.2 |
| `EMIT_L2B_CH4ENH_002_20250323T212330_2508214_007` | positive_validation | 10 | 0 / 17 | 13,134.7 |
| `EMIT_L2B_CH4ENH_002_20240216T201146_2404713_018` | control_validation | 0 | 0 / 14 | 2,545.1 |
| `EMIT_L2B_CH4ENH_002_20241004T165203_2427811_009` | control_validation | 0 | 0 / 18 | 93.1 |
| `EMIT_L2B_CH4ENH_002_20231224T174545_2335812_007` | search | 3 | 0 / 27 | 6,867.0 |
| `EMIT_L2B_CH4ENH_002_20240127T195904_2402713_008` | search | 0 | 0 / 18 | 70.4 |
| `EMIT_L2B_CH4ENH_002_20240212T214808_2404314_022` | search | 1 | 0 / 16 | 3,157.6 |
| `EMIT_L2B_CH4ENH_002_20240212T214820_2404314_023` | search | 3 | 0 / 39 | 6,186.2 |
| `EMIT_L2B_CH4ENH_002_20240212T214832_2404314_024` | search | 2 | 0 / 44 | 6,078.4 |
| `EMIT_L2B_CH4ENH_002_20240212T214843_2404314_025` | search | 0 | 0 / 30 | 689.1 |
| `EMIT_L2B_CH4ENH_002_20240727T195453_2420913_014` | search | 0 | 25 / 5 | 708.0 |
| `EMIT_L2B_CH4ENH_002_20240827T155722_2424010_002` | search | 1 | 0 / 39 | 3,555.0 |
| `EMIT_L2B_CH4ENH_002_20241004T165227_2427811_011` | search | 1 | 0 / 27 | 6,907.7 |
| `EMIT_L2B_CH4ENH_002_20241130T180310_2433512_007` | search | 0 | 25 / 30 | 1,227.9 |
| `EMIT_L2B_CH4ENH_002_20250412T213417_2510214_032` | search | 1 | 25 / 24 | 3,614.5 |
| `EMIT_L2B_CH4ENH_002_20250420T182309_2511012_030` | search | 1 | 0 / 17 | 5,832.2 |
| `EMIT_L2B_CH4ENH_002_20250613T205432_2516413_032` | search | 0 | 0 / 11 | 1,606.6 |
| `EMIT_L2B_CH4ENH_002_20250727T193810_2520813_006` | search | 0 | 25 / 4 | 3,092.4 |
| `EMIT_L2B_CH4ENH_002_20250808T144449_2522010_003` | search | 0 | 0 / 43 | 867.2 |
| `EMIT_L2B_CH4ENH_002_20250922T204933_2526514_006` | search | 0 | 25 / 77 | 136.1 |

Areas above were computed from the frozen CMR polygon vertices in EPSG:4326, clipped to the fixed bounding box, then projected to UTM zone 13N (EPSG:32613). They measure approximate geometric coverage before cloud, water, nodata or sensitivity masking. The region covers approximately **41,897 km²**; the union of selected geometric footprints covers approximately **37,014 km²**. Neither number establishes usable observation coverage. Actual valid-pixel exposure must be calculated from the acquired arrays.

The 20 timestamps occur on **16 acquisition dates**, including four adjacent granules on 12 February 2024 and two granules on 4 October 2024. They must not be described as 20 independent temporal revisits. One control covers only about **93 km²** within the region, and some search scenes likewise contribute small boundary slivers. The quality-valid area of that control may therefore be much smaller than its nominal full scene.

## Catalog matching risks

1. The regional Carbon Mapper snapshot contains **121 EMIT CH4 records**, with returned count equal to reported `bbox_count` and no further pagination needed for that query. It is complete for the queried provider/filter snapshot, not a complete methane inventory.
2. That query filters **source points inside the region**. A plume or component inside the region can originate just outside it. Per-scene catalog queries without a point bounding-box restriction, or a documented comparison buffer, are needed before treating boundary candidates as unmatched. This does not require widening the analysis region.
3. Use scene identity, observation time and geographic geometry together. A source point on the same acquisition timestamp may be many kilometers from a selected plume complex. Timestamp equality alone cannot establish a match.
4. Carbon Mapper and NASA entries from the same EMIT radiance acquisition are processing comparisons, not independent satellite corroboration. Their different collection and processing versions can create catalog discrepancies without a new emission event.
5. Multiple source heads can correspond to one NASA plume complex, and adjacent granules can observe related emissions. Deduplicate candidate geometry and scene relationships before counting events.
6. Carbon Mapper `published_plume_count` can refer to all gases or the provider's scene-level count convention. A positive methane label was independently checked against explicit `gas=CH4` catalog records; nonzero scene counts elsewhere in the sample do not establish in-region methane detections.
7. A zero catalog count has no known sensitivity guarantee. Controls need valid-pixel, uncertainty, sensitivity and artifact assessment before supporting a false-positive statement. Two controls are insufficient for a broad specificity estimate.
8. Published facilities, attribution, emission rates, novelty and atmospheric plume evidence remain separate claims. This manifest establishes none of the first four by itself.

## Supplementary public-crop limitations

Two NASA PLM V002 numeric exports were acquired during access diagnosis. The server returns float32 methane values in band 1 and an alpha-like validity channel in band 2, while the exported GeoTIFF advertises no nodata value and Rasterio can report every pixel as valid. Correct reading explicitly requires positive alpha, finite band-1 values and exclusion of the source `-9999` sentinel.

`EMIT_L2B_CH4PLM_002_20241130T180310_003723` has 9,843 valid pixels across its full delivered product, but **zero valid pixels inside the investigation region**; it must be excluded from useful regional observations. `EMIT_L2B_CH4PLM_002_20241004T165227_003636` has 269 valid pixels inside the region. Both are already published NASA products.

NASA delivery code applies a threshold plus manual plume mask before writing PLM raster support: [pinned processing source, lines 539–588](https://github.com/emit-sds/emit-sds-tgp/blob/6751936c9957af01ac7dc8db20b32ca8d1f45ed2/src/scrape_refine_upload.py#L539-L588). Therefore these masked crops cannot provide unbiased background controls or establish detector sensitivity, false-positive performance, catalog completeness or novelty. The complete full-scene ENH products are the primary investigation inputs.

## Reproducibility pointers

- Reuse the frozen manifest rather than rerunning a mutable latest-data query for this experiment.
- Preserve the acquisition ledger's URL, byte count, SHA-256 and download time; the current ledger governs acquisition completion.
- Compare native raster grids and quality-mask georeferencing before combining arrays.
- Report pixel-quality exposure and failed checks separately from selected-scene counts.
- Retain failed access and supplementary-crop outcomes as access experiments; do not reuse them as plume-discovery evidence.

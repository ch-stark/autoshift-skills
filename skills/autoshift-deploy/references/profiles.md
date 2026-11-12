# Clusterset profiles

The shipped profiles in `autoshift/values/clustersets/`. Compose them in `valueFiles`, always after
`values/global.yaml`. Later files win.

| Profile | Use for | Notes |
|---|---|---|
| `hub-minimal.yaml` | first smoke test | GitOps and ACM only. Proves installation, places few policies |
| `hub.yaml` | a real evaluation of a cloud hub | Infrastructure and storage nodes, OpenShift Data Foundation, most components. Needs quota |
| `hub-hardened.yaml` | compliance enforced, not only reported | Layer after `hub.yaml`; not standalone |
| `hub-ambient.yaml` | Service Mesh ambient mode | Minimal hub plus mesh dependencies, ODF and storage nodes |
| `hub-baremetal-compact.yaml` | three-node bare metal hub | Excludes infra and worker node policies; MetalLB |
| `hub-baremetal-sno.yaml` | single node bare metal hub | Excludes infra and worker node policies; MetalLB |
| `managed.yaml` | managed clusters | A `managedClusterSets` profile; pair with any hub profile |
| `sbx.yaml` | sandbox managed clusters | Smaller managed profile |
| `hubofhubs.yaml`, `hub1.yaml`, `hub2.yaml` | hub of hubs | Top hub plus two managed hubs; read `docs/hub-of-hubs.md` |
| `non-ha-acps-odf-custom-example.yaml` | example only | Shows config-driven ODF and local storage overrides |
| `_example.yaml` | reference catalog | Every declared label and config key. Not a deployable profile |

## Picking

| Environment | Start with |
|---|---|
| Cloud hub, first look | `hub-minimal.yaml` |
| Cloud hub, real evaluation | `hub.yaml` + `managed.yaml` |
| Bare metal, three nodes | `hub-baremetal-compact.yaml` |
| Single node | `hub-baremetal-sno.yaml` |
| Hub of hubs | `hubofhubs.yaml` + `hub1.yaml` (+ `hub2.yaml`) + `managed.yaml` |

## Rules for a person's own values

- Start from the closest profile; record only the differences in a per-cluster or per-site file.
- `hubClusterSets.<name>` and `managedClusterSets.<name>` names become ACM cluster sets. The name
  plus any release suffix must stay within 63 characters.
- Labels: `labels:` under the cluster set, quoted strings. Data: `config:` beside it.
- Enabling an operator means setting all its labels (`<op>`, `-subscription-name`, `-channel`,
  `-source`, `-source-namespace`); copy them from `_example.yaml`.
- Deleting a key from values stops AutoShift managing that setting; it does not undo it on the
  cluster. Turning a component off cleanly uses its `uninstall` value where the policy supports one.
- `metallb` only where no cloud load balancer controller exists (bare metal, on-premises).

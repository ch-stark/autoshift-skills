# Disconnected installs

Do these before phase 2. Read `docs/releases.md` and
`policies/stable/disconnected-mirror/README.md` in the checkout for the full procedure.

1. **Mirror first.** The bootstrap charts install from catalogs that do not exist in an air gap.
   Create the mirrored `CatalogSource` objects (the `cs-*.yaml` files `oc mirror` writes), then set
   `source` in `advanced-cluster-management/values.yaml` and
   `policies/stable/openshift-gitops/values.yaml` to that catalog. AutoShift later moves both
   subscriptions to its own mirrored catalogs.
2. **CLI image.** The bootstrap Jobs resolve their CLI image from the cluster's own `openshift/cli`
   ImageStream, which an ImageDigestMirrorSet rewrites, so no internal registry is needed. To pin a
   mirrored image instead, pass the same `--set image=<registry>/openshift4/ose-cli:<tag>` to both
   bootstrap installs.
3. **Values.** One `config.disconnected` block (mirror registry URL, CA, sources, catalogs) serves
   both the `disconnected-mirror` and `cluster-install` policies. Copy its shape from
   `autoshift/values/clustersets/_example.yaml`. Reference CA material through its `caRef` form
   rather than pasting large blocks when a ConfigMap already holds it.
4. **Source of AutoShift itself.** Mirror the git repository (source) or the OCI charts (release) to
   a location the hub can reach, and point the Application there.
5. **Operator images not in a catalog.** Some components pull images by tag (for example database
   images). Check the release imageset (`make generate-imageset`) covers everything enabled.

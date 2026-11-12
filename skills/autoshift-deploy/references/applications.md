# The AutoShift Application

Pick the shape that matches the install method and where values live. Replace `<...>`. The
Application name decides the policy namespace (`policies-<name>`) and is 11 characters or fewer.

## Source, in-repo or fork values

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: autoshift
  namespace: openshift-gitops
spec:
  project: default
  destination:
    namespace: openshift-gitops
    server: https://kubernetes.default.svc
  source:
    repoURL: <https://github.com/auto-shift/autoshiftv2.git, or their fork>
    targetRevision: <main, a tag, or a branch>
    path: autoshift
    helm:
      valueFiles:
        - values/global.yaml
        - values/clustersets/<hub-profile>.yaml
        - values/clustersets/managed.yaml
      parameters:
        - name: autoshiftGitRepo
          value: $ARGOCD_APP_SOURCE_REPO_URL
        - name: autoshiftGitBranchTag
          value: $ARGOCD_APP_SOURCE_TARGET_REVISION
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
```

Use a URL the hub can reach. A git server hosted on another cluster is not reachable from a fresh
hub; the public upstream or their fork on a public host is. Applied through a shell heredoc, escape
the variables as `\$ARGOCD_APP_SOURCE_REPO_URL` so the shell leaves them for Argo CD.

## Source, values in their own repository (recommended for production)

```yaml
spec:
  sources:
    - repoURL: <their values repository>
      targetRevision: main
      ref: siteValues
    - repoURL: https://github.com/auto-shift/autoshiftv2.git
      targetRevision: <tag or main>
      path: autoshift
      helm:
        valueFiles:
          - $siteValues/global.yaml
          - $siteValues/clustersets/<hub>.yaml
          - $siteValues/clusters/<cluster>.yaml
        parameters:
          - name: autoshiftGitRepo
            value: $ARGOCD_APP_SOURCE_REPO_URL
          - name: autoshiftGitBranchTag
            value: $ARGOCD_APP_SOURCE_TARGET_REVISION
```

The rest is as in the previous shape. The values source must be git. A private values repository
must be registered with Argo CD first.

## OCI release

```yaml
spec:
  project: default
  source:
    repoURL: quay.io/autoshift
    chart: autoshift
    targetRevision: "<X.Y.Z>"
    helm:
      valueFiles:
        - values/global.yaml
        - values/clustersets/<hub-profile>.yaml
        - values/clustersets/managed.yaml
      values: |
        autoshiftOciRepo: oci://quay.io/autoshift/policies
      parameters:
        - name: autoshiftOciVersion
          value: $ARGOCD_APP_SOURCE_TARGET_REVISION
  destination:
    server: https://kubernetes.default.svc
    namespace: openshift-gitops
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

`autoshiftOciVersion` is required; never use a mutable tag. The release scripts are an alternative:
`install-bootstrap.sh` then `install-autoshift.sh <hub|minimal|sbx|hubofhubs>` from the GitHub
release.

## Development only: Helm from a working copy

```bash
helm upgrade --install autoshift ./autoshift -n openshift-gitops \
  --set autoshiftGitRepo=<repo URL> --set autoshiftGitBranchTag=<branch> \
  -f autoshift/values/global.yaml -f autoshift/values/clustersets/<hub>.yaml
```

Values are read locally; policy templates still come from the git repository and branch named.
There is no `autoshift` Application in this mode; verify the `autoshift-policies` ApplicationSet.

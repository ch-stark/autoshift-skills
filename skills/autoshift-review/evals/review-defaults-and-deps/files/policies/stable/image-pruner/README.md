# image-pruner

Configures the image pruner on clusters labelled `autoshift.io/image-pruner: 'true'`, after
`policy-image-registry-storage` is Compliant.

## Configuration

```yaml
config:
  image-pruner:
    schedule: '0 0 * * *'
    suspend: false
    keepTagRevisions: 3
```

// Prints the template function names available in ACM 2.17 policy templates,
// from the go-template-utils version in go.mod (shared/acm-baseline.yaml records which).
// Output: one "<name>\t<source>" per line, sorted.
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"

	"github.com/stolostron/go-template-utils/v7/pkg/templates"
)

func main() {
	names := map[string]string{}
	for _, f := range templates.AvailableSprigFunctions() {
		names[f] = "sprig"
	}
	// ACM-specific functions are registered in a map literal inside ResolveTemplate.
	src, err := os.ReadFile(filepath.Join(os.Args[1], "pkg/templates/templates.go"))
	if err != nil {
		panic(err)
	}
	for _, m := range regexp.MustCompile(`(?m)^\s+"([a-zA-Z0-9]+)":\s+(t\.|getSprigFunc|[a-z])`).FindAllStringSubmatch(string(src), -1) {
		names[m[1]] = "acm"
	}
	// Added outside the literal: protect (hub, encryption only) and skipObject (config-policy-controller).
	names["protect"] = "acm-hub"
	names["skipObject"] = "acm-local"
	keys := make([]string, 0, len(names))
	for k := range names {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		fmt.Printf("%s\t%s\n", k, names[k])
	}
}

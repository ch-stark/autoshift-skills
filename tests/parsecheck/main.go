package main

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"strings"
	"text/template"
)

// Parse-check eval fixtures against the ACM 2.17 function names. Hub pass with {{hub hub}} delimiters, then local pass on what remains.
func main() {
	funcs := template.FuncMap{}
	f, _ := os.Open(os.Args[1])
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		funcs[strings.Split(sc.Text(), "\t")[0]] = func(...interface{}) interface{} { return nil }
	}
	bad := 0
	for _, p := range os.Args[2:] {
		b, _ := os.ReadFile(p)
		s := string(b)
		if _, err := template.New("hub").Delims("{{hub", "hub}}").Funcs(funcs).Parse(s); err != nil {
			fmt.Println("HUB  ", p, err)
			bad++
			continue
		}
		local := regexp.MustCompile(`(?s)\{\{hub.*?hub\}\}`).ReplaceAllString(s, "X")
		if _, err := template.New("local").Funcs(funcs).Parse(local); err != nil {
			fmt.Println("LOCAL", p, err)
			bad++
			continue
		}
		fmt.Println("ok   ", p)
	}
	os.Exit(bad)
}

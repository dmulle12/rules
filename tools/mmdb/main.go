// Build a minimal MaxMind-format country database (chnroutes.mmdb)
// from a plain CIDR list, e.g. Loyalsoldier/geoip text/cn.txt.
// Every listed network is mapped to country CN; everything else
// has no record.
//
// Usage: mmdb-build <cidr-list.txt> <out.mmdb>
package main

import (
	"bufio"
	"fmt"
	"net"
	"os"
	"strings"

	"github.com/maxmind/mmdbwriter"
	"github.com/maxmind/mmdbwriter/inserter"
	"github.com/maxmind/mmdbwriter/mmdbtype"
)

// chinaRecord mirrors the GeoLite2-Country record layout so readers
// (Surge GEOIP rules, geoip2, ...) see a familiar structure.
func chinaRecord() mmdbtype.DataType {
	return mmdbtype.Map{
		"country": mmdbtype.Map{
			"geoname_id":           mmdbtype.Uint32(1814991),
			"is_in_european_union": mmdbtype.Bool(false),
			"iso_code":             mmdbtype.String("CN"),
			"names": mmdbtype.Map{
				"de":    mmdbtype.String("China"),
				"en":    mmdbtype.String("China"),
				"es":    mmdbtype.String("China"),
				"fr":    mmdbtype.String("Chine"),
				"ja":    mmdbtype.String("中国"),
				"pt-BR": mmdbtype.String("China"),
				"ru":    mmdbtype.String("China"),
				"zh-CN": mmdbtype.String("中国"),
			},
		},
	}
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: mmdb-build <cidr-list.txt> <out.mmdb>")
		os.Exit(2)
	}

	writer, err := mmdbwriter.New(mmdbwriter.Options{
		DatabaseType: "GeoLite2-Country",
		RecordSize:   24,
		Languages:    []string{"de", "en", "es", "fr", "ja", "pt-BR", "ru", "zh-CN"},
		Description: map[string]string{
			"en": "China routes (CN) IP database",
		},
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "mmdbwriter.New:", err)
		os.Exit(1)
	}

	in, err := os.Open(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, "open input:", err)
		os.Exit(1)
	}
	defer in.Close()

	record := chinaRecord() // immutable: safe to reuse for every insert
	inserted := 0
	scanner := bufio.NewScanner(in)
	scanner.Buffer(make([]byte, 1024*1024), 1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		_, network, err := net.ParseCIDR(line)
		if err != nil {
			fmt.Fprintln(os.Stderr, "skip invalid line:", line)
			continue
		}
		if err := writer.InsertFunc(network, inserter.ReplaceWith(record)); err != nil {
			fmt.Fprintln(os.Stderr, "insert:", err)
			os.Exit(1)
		}
		inserted++
	}
	if err := scanner.Err(); err != nil {
		fmt.Fprintln(os.Stderr, "read input:", err)
		os.Exit(1)
	}

	out, err := os.Create(os.Args[2])
	if err != nil {
		fmt.Fprintln(os.Stderr, "create output:", err)
		os.Exit(1)
	}
	if _, err := writer.WriteTo(out); err != nil {
		fmt.Fprintln(os.Stderr, "write mmdb:", err)
		os.Exit(1)
	}
	if err := out.Close(); err != nil {
		fmt.Fprintln(os.Stderr, "close output:", err)
		os.Exit(1)
	}
	fmt.Printf("inserted %d networks -> %s\n", inserted, os.Args[2])
}

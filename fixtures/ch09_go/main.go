// Chapter 9 parser differential helper: reads base64 lines, prints the (invoice_id, payee_id, amount_cents) view of Go's encoding/json.
package main

import (
	"bufio"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
)

type R struct {
	InvoiceID string      `json:"invoice_id"`
	PayeeID   string      `json:"payee_id"`
	Amount    json.Number `json:"amount_cents"`
}

func main() {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1<<20), 1<<20)
	for sc.Scan() {
		b, _ := base64.StdEncoding.DecodeString(sc.Text())
		var r R
		if err := json.Unmarshal(b, &r); err != nil {
			fmt.Println(`null`)
			continue
		}
		out, _ := json.Marshal([]string{r.InvoiceID, r.PayeeID, r.Amount.String()})
		fmt.Println(string(out))
	}
}

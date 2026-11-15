"""Chapter 37: what the author read, and the mapping he wrote.  Items are copied from the sources named in STANDARDS (retrieved 2026-11-13); `read` says how much of each was read.
The mapping is the author's judgement; it is data so that it can be checked, diffed and signed with the bundle."""
from .crosswalk import Standard, Item, Row, Catalogue

R = "2026-11-13"
STANDARDS = [
 Standard("LLM25", "OWASP Top 10 for LLM Applications", "2025", "2024-11 (v2025)", "final", "genai.owasp.org/llm-top-10/", "TITLES", R),
 Standard("LLM23", "OWASP Top 10 for LLM Applications", "2023-24 (v1.1)", "2023-10", "superseded", "genai.owasp.org/llm-top-10-2023-24/", "TITLES", R, complete=False),   # kept for `drift` only: a gap in a superseded edition means nothing
 Standard("ASI26", "OWASP Top 10 for Agentic Applications", "2026", "2025-12-09", "final", "genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/", "TITLES", R),
 Standard("N600", "NIST AI 600-1 Generative AI Profile (risks)", "July 2024", "2024-07-26", "final", "nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf", "FULL_TEXT", R),
 Standard("I42K", "ISO/IEC 42001 Annex A", "2023", "2023-12", "final", "iso.org (paywalled); control list read from two secondary pages", "SECONDARY", R),
 Standard("EUAI", "EU AI Act (Regulation (EU) 2024/1689)", "OJ 2024, as amended by the Digital Omnibus on AI (2026)", "2024-07-12; omnibus 2026-07", "in force; high-risk dates moved", "artificialintelligenceact.eu article pages; Council and Commission pages", "FULL_TEXT", R, complete=False, binding=True),
 Standard("ATLS", "MITRE ATLAS", "v2026.10", "2026-10-28", "living", "github.com/mitre-atlas/atlas-data CHANGELOG.md; technique names via a secondary page", "SECONDARY", R, complete=False),
]
def _i(s, rows, from_date=""): return [Item(s, a, b, from_date) for a, b in rows]
ITEMS = (
 _i("LLM25", [("LLM01", "Prompt Injection"), ("LLM02", "Sensitive Information Disclosure"), ("LLM03", "Supply Chain"), ("LLM04", "Data and Model Poisoning"), ("LLM05", "Improper Output Handling"),
              ("LLM06", "Excessive Agency"), ("LLM07", "System Prompt Leakage"), ("LLM08", "Vector and Embedding Weaknesses"), ("LLM09", "Misinformation"), ("LLM10", "Unbounded Consumption")]) +
 _i("LLM23", [("LLM01", "Prompt Injection"), ("LLM02", "Insecure Output Handling"), ("LLM03", "Training Data Poisoning"), ("LLM04", "Model Denial of Service"), ("LLM05", "Supply Chain Vulnerabilities"),
              ("LLM06", "Sensitive Information Disclosure"), ("LLM07", "Insecure Plugin Design"), ("LLM08", "Excessive Agency"), ("LLM09", "Overreliance"), ("LLM10", "Model Theft")]) +
 _i("ASI26", [("ASI01", "Agent Goal Hijack"), ("ASI02", "Tool Misuse and Exploitation"), ("ASI03", "Identity and Privilege Abuse"), ("ASI04", "Agentic Supply Chain"), ("ASI05", "Unexpected Code Execution"),
              ("ASI06", "Memory and Context Poisoning"), ("ASI07", "Insecure Inter-Agent Communication"), ("ASI08", "Cascading Failures"), ("ASI09", "Human-Agent Trust Exploitation"), ("ASI10", "Rogue Agents")]) +
 _i("N600", [("R01", "CBRN Information or Capabilities"), ("R02", "Confabulation"), ("R03", "Dangerous, Violent, or Hateful Content"), ("R04", "Data Privacy"), ("R05", "Environmental Impacts"),
             ("R06", "Harmful Bias or Homogenization"), ("R07", "Human-AI Configuration"), ("R08", "Information Integrity"), ("R09", "Information Security"), ("R10", "Intellectual Property"),
             ("R11", "Obscene, Degrading, and/or Abusive Content"), ("R12", "Value Chain and Component Integration")]) +
 _i("I42K", [("A.2.2", "AI policy"), ("A.2.3", "Alignment with other organisational policies"), ("A.2.4", "Review of the AI policy"), ("A.3.2", "AI roles and responsibilities"), ("A.3.3", "Reporting of concerns"),
             ("A.4.2", "Resource documentation"), ("A.4.3", "Data resources"), ("A.4.4", "Tooling resources"), ("A.4.5", "System and computing resources"), ("A.4.6", "Human resources"),
             ("A.5.2", "AI system impact assessment process"), ("A.5.3", "Documentation of AI system impact assessments"), ("A.5.4", "Assessing AI system impact on individuals or groups of individuals"), ("A.5.5", "Assessing societal impacts of AI systems"),
             ("A.6.1.2", "Objectives for responsible development of AI system"), ("A.6.1.3", "Processes for responsible design and development of AI systems"), ("A.6.2.2", "AI system requirements and specification"),
             ("A.6.2.3", "Documentation of AI system design and development"), ("A.6.2.4", "AI system verification and validation"), ("A.6.2.5", "AI system deployment"), ("A.6.2.6", "AI system operation and monitoring"),
             ("A.6.2.7", "AI system technical documentation"), ("A.6.2.8", "AI system recording of event logs"), ("A.7.2", "Data for development and enhancement of AI system"), ("A.7.3", "Acquisition of data"),
             ("A.7.4", "Quality of data for AI systems"), ("A.7.5", "Data provenance"), ("A.7.6", "Data preparation"), ("A.8.2", "System documentation and information for users"), ("A.8.3", "External reporting"),
             ("A.8.4", "Communication of incidents"), ("A.8.5", "Information for interested parties"), ("A.9.2", "Processes for responsible use of AI systems"), ("A.9.3", "Objectives for responsible use of AI system"),
             ("A.9.4", "Intended use of the AI system"), ("A.10.2", "Allocation of responsibilities"), ("A.10.3", "Suppliers"), ("A.10.4", "Customers")]) +
 _i("EUAI", [("Art4", "AI literacy"), ("Art50", "Transparency obligations for providers and deployers of certain AI systems")], "2026-08-02") +
 _i("EUAI", [("Art9", "Risk management system"), ("Art12", "Record-keeping"), ("Art14", "Human oversight"), ("Art15", "Accuracy, robustness and cybersecurity"), ("Art26", "Obligations of deployers of high-risk AI systems")], "2027-12-02") +
 _i("EUAI", [("Art73", "Reporting of serious incidents")], "2027-12-02") +
 _i("ATLS", [("AML.T0051", "LLM Prompt Injection"), ("AML.T0053", "AI Agent Tool Invocation"), ("AML.T0080", "AI Agent Context Poisoning"), ("AML.T0086", "Exfiltration via AI Agent Tool Invocation"), ("AML.T0110", "AI Agent Tool Poisoning")])
)
CAT = Catalogue(STANDARDS, ITEMS)
EDN = {s.id: s.edition for s in STANDARDS}

# --- the mapping: (control, standard, item, relation, limit sentence) -------------------------------------------------
_ROWS = [
 ("C01", "ASI26", "ASI09", "PARTIAL", "the callback is a person confirming out of band; nothing tests whether the person is persuaded by a forged callback number"),
 ("C01", "ASI26", "ASI02", "PARTIAL", "covers the bank-change path only"),
 ("C01", "LLM25", "LLM06", "ADDRESSES", "one effect class (payment), one tenant"),
 ("C02", "ASI26", "ASI02", "ADDRESSES", "payment classes the author built; a model second reviewer tried live on one prompt"),
 ("C02", "LLM25", "LLM06", "ADDRESSES", "payment tool only; draft and send are other controls"),
 ("C02", "LLM25", "LLM05", "PARTIAL", "the model's proposed amount is checked against the invoice; other outputs are not"),
 ("C02", "N600", "R02", "PARTIAL", "checks the amount and payee fields of the proposal, not the whole text the model writes"),
 ("C02", "I42K", "A.6.2.4", "EVIDENCE_FOR", "verification of one control by author-built cases"),
 ("C03", "ASI26", "ASI10", "PARTIAL", "makes a rogue agent's actions findable afterwards; does not stop one"),
 ("C03", "I42K", "A.6.2.8", "EVIDENCE_FOR", "one chain implementation; anchor service simulated"),
 ("C03", "EUAI", "Art12", "ALIGNED_WITH", "text applies to high-risk systems from 2027-12-02; Quill is not classified as one by the author [VERIFY with counsel]"),
 ("C04", "ASI26", "ASI01", "PARTIAL", "bounds where a hijacked agent can send data; does not stop the hijack"),
 ("C04", "ASI26", "ASI02", "PARTIAL", "mail destination only"),
 ("C04", "LLM25", "LLM02", "ADDRESSES", "unlisted recipients and domains; content of an allowed message is not inspected for secrets"),
 ("C04", "LLM25", "LLM01", "PARTIAL", "limits the effect of an injection that reaches the model; does not detect it"),
 ("C04", "N600", "R04", "PARTIAL", "covers outbound mail only; no inspection of stored data"),
 ("C04", "ATLS", "AML.T0086", "ADDRESSES", "email egress only"),
 ("C05", "LLM25", "LLM10", "ADDRESSES", "per-task counters in lab loadouts; provider-side spend caps are not tested"),
 ("C05", "ASI26", "ASI08", "PARTIAL", "stops loops and fan-out; says nothing about a dependency that fails"),
 ("C06", "ASI26", "ASI02", "ADDRESSES", "loadouts and registry inventory checked at build; runtime tool lists are Chapter 25's"),
 ("C06", "ASI26", "ASI03", "PARTIAL", "limits which tools a task can name; the credential is C15's"),
 ("C06", "LLM25", "LLM06", "ADDRESSES", "inventory covers Quill's tools only"),
 ("C06", "I42K", "A.4.4", "EVIDENCE_FOR", "the registry is a list of tooling resources; it is not an assessment of them"),
 ("C07", "ASI26", "ASI06", "ADDRESSES", "trust labels on writes; lab poisoning attempts the author wrote"),
 ("C07", "LLM25", "LLM04", "PARTIAL", "covers memory writes; no training or fine-tuning data is in scope"),
 ("C07", "LLM25", "LLM08", "PARTIAL", "pooled-index tenancy is Chapter 11's; embedding inversion is untested"),
 ("C07", "ATLS", "AML.T0080", "ADDRESSES", "memory writes in the lab only"),
 ("C08", "ASI26", "ASI04", "ADDRESSES", "description and schema pinning for MCP tools; implementation code of a server is not checked"),
 ("C08", "LLM25", "LLM03", "PARTIAL", "tool descriptions only; model weights and datasets are out of scope"),
 ("C08", "N600", "R12", "PARTIAL", "pins what a third-party tool says about itself, not what it does"),
 ("C08", "ATLS", "AML.T0110", "ADDRESSES", "descriptor-level poisoning; runtime-response poisoning is Chapter 25's untested corner"),
 ("C09", "ASI26", "ASI01", "PARTIAL", "a prompt change cannot ship without the gate; the gate's cases are the author's"),
 ("C09", "LLM25", "LLM07", "PARTIAL", "prompts are versioned and gated for behaviour (Chapter 18); no test tries to extract one, and no prompt is claimed to be free of anything an attacker could use"),
 ("C09", "I42K", "A.6.2.5", "EVIDENCE_FOR", "release gate for prompts only"),
 ("C09", "I42K", "A.6.2.4", "EVIDENCE_FOR", "baseline runs against one model"),
 ("C10", "ASI26", "ASI04", "ADDRESSES", "floating specs, source change and widened permission; 192 author-built cases"),
 ("C10", "LLM25", "LLM03", "ADDRESSES", "skills and plugins; not base models"),
 ("C10", "I42K", "A.10.3", "PARTIAL", "a lock on what is installed; not an assessment of the supplier"),
 ("C11", "ASI26", "ASI05", "ADDRESSES", "one machine, one kernel; deny-list filter"),
 ("C11", "LLM25", "LLM05", "PARTIAL", "code written by a model is run in the sandbox; other outputs are not"),
 ("C12", "ASI26", "ASI10", "PARTIAL", "detects effects, not intent; 25 of 36 simulated attack payments"),
 ("C12", "ASI26", "ASI08", "PARTIAL", "a detector for an anomaly after it started; not a boundary"),
 ("C12", "I42K", "A.6.2.6", "EVIDENCE_FOR", "monitoring of effects in a simulated stream"),
 ("C12", "N600", "R09", "PARTIAL", "detection of misuse of the agent's own tools"),
 ("C13", "I42K", "A.8.4", "EVIDENCE_FOR", "a recorded case with owner and deadline; notices written by the author"),
 ("C13", "I42K", "A.8.3", "PARTIAL", "records what was sent; whether it had to be sent is a legal question"),
 ("C13", "EUAI", "Art73", "ALIGNED_WITH", "the 15-day outer limit in Art 73(2) is for providers of high-risk systems; not applicable to Quill as classified [VERIFY with counsel]"),
 ("C13", "ASI26", "ASI10", "PARTIAL", "containment of a compromised agent in the lab"),
 ("C14", "I42K", "A.6.2.4", "EVIDENCE_FOR", "mutation score of the author's own tests"),
 ("C15", "ASI26", "ASI03", "ADDRESSES", "task tokens in a lab with no real identity provider"),
 ("C15", "LLM25", "LLM06", "PARTIAL", "limits the authority a token carries; whether the tool needs less is C06's"),
 ("C15", "I42K", "A.9.2", "PARTIAL", "a process for responsible use exists for the payment path only"),
 ("C16", "ASI26", "ASI09", "PARTIAL", "the approval names its effect; whether the person reads it is untested"),
 ("C16", "ASI26", "ASI02", "PARTIAL", "a changed effect needs a new approval"),
 ("C16", "N600", "R07", "PARTIAL", "reviewers are simulated; automation bias is not measured"),
 ("C16", "EUAI", "Art14", "ALIGNED_WITH", "Art 14(4)(d)(e) ask for the ability to override and to stop; applies from 2027-12-02 to high-risk systems [VERIFY]"),
 ("C17", "I42K", "A.6.2.6", "EVIDENCE_FOR", "scope of re-verification for a change, not the verification"),
 ("C17", "I42K", "A.6.2.5", "PARTIAL", "release scope for a change to a module"),
 ("C18", "ASI26", "ASI08", "PARTIAL", "12 of 36 dependency-and-fault cells were drilled in replay; 24 untested"),
 ("C18", "LLM25", "LLM10", "PARTIAL", "retry storms and breaker flapping were simulated; provider rate limits were not"),
 ("C18", "ASI26", "ASI09", "PARTIAL", "an approval queue under load was simulated with reviewers assumed correct"),
 ("C18", "EUAI", "Art15", "ALIGNED_WITH", "Art 15(4) asks for resilience and mentions fail-safe plans; applies from 2027-12-02 to high-risk systems [VERIFY]"),
 ("C18", "I42K", "A.6.2.6", "EVIDENCE_FOR", "degraded modes are declared and recorded; production outages are not yet in the evidence"),
]
# Chapter 38: C19, the agent boundary (typed signed envelope, attenuating grant, taint, card pin, budgets).  Kept apart so that Chapter 37's 63 rows stay reproducible; rows38() is rows() plus these.
_ROWS38 = [
 ("C19", "ASI26", "ASI07", "PARTIAL", "envelope, verb ACL, grant and taint were exercised in a simulated six-agent topology and in live three-agent pipelines on one small model; one shared key, no transport security, no remote agent under Ledgerly's control"),
 ("C19", "ASI26", "ASI03", "PARTIAL", "the grant can only shrink along a delegation and is intersected with the receiver's own authority; the identity behind each agent is a name in a registry, not a credential issued to it (C15)"),
 ("C19", "ASI26", "ASI08", "PARTIAL", "path and task budgets, cycle and fan-out limits stop simulated loops; a real provider outage during a loop was not drilled"),
 ("C19", "ASI26", "ASI10", "PARTIAL", "a pinned card catches a changed card; an agent that was compromised and kept its card is not caught by the pin"),
 ("C19", "ASI26", "ASI01", "PARTIAL", "keeps untrusted text out of the instruction channel between agents; a model that reads the data channel can still be steered by it"),
 ("C19", "ASI26", "ASI04", "PARTIAL", "pins the card of a remote agent; does not read what the remote agent is made of"),
 ("C19", "LLM25", "LLM01", "PARTIAL", "indirect injection that crosses an agent boundary as text is typed out of the instruction channel; injection into a model that must read the data is not prevented"),
 ("C19", "LLM25", "LLM06", "PARTIAL", "agency of a downstream agent is bounded by the task grant; the grant is only as small as the person who wrote the task made it"),
 ("C19", "LLM25", "LLM10", "PARTIAL", "message and path budgets bound consumption in simulated loops; per-tenant spend caps are the gateway's (C09)"),
 ("C19", "N600", "R09", "PARTIAL", "message integrity and replay protection exist in simulation; confidentiality in transit and key management do not"),
 ("C19", "N600", "R12", "PARTIAL", "a remote agent is a component from a third party; the card pin records which one, not whether it is sound"),
 ("C19", "I42K", "A.10.3", "EVIDENCE_FOR", "the registry of admitted agents, their cards and their pinned digests are suppliers' records of a kind; the supplier review itself is not part of this control"),
 ("C19", "EUAI", "Art15", "ALIGNED_WITH", "Art 15(5) asks for resilience against attempts by third parties to alter use or outputs; applies from 2027-12-02 to high-risk systems [VERIFY]"),
]
def rows38(edition_override: dict | None = None) -> list[Row]:
    e = dict(EDN); e.update(edition_override or {})
    return rows(edition_override) + [Row(c, s, i, e[s], rel, lim, CAT.items[f"{s}:{i}"].title if f"{s}:{i}" in CAT.items else "") for c, s, i, rel, lim in _ROWS38]
def rows(edition_override: dict | None = None) -> list[Row]:
    e = dict(EDN); e.update(edition_override or {})
    return [Row(c, s, i, e[s], rel, lim, CAT.items[f"{s}:{i}"].title if f"{s}:{i}" in CAT.items else "") for c, s, i, rel, lim in _ROWS]
# Chapter 40: C20, model provenance (weights file checks, the model bill, and the two trigger searches).  rows40() is rows38() plus these 11.
_ROWS40 = [
 ("C20", "LLM25", "LLM03", "PARTIAL", "pins, scans and records the files of the models Ledgerly loads itself; the hosted model's weights are not visible, so for them it records the served id and a behaviour fingerprint only"),
 ("C20", "LLM25", "LLM04", "PARTIAL", "a training-set audit and a trigger search found a planted trigger at some rates in one synthetic classifier; pre-training data of a vendor's model is out of reach and no fine-tune of a large model was run"),
 ("C20", "ASI26", "ASI04", "PARTIAL", "extends C08 and C10 from tools and skills to model files; a model that was backdoored upstream and then pinned is pinned as it is"),
 ("C20", "ASI26", "ASI10", "PARTIAL", "an agent whose weights carry a hidden behaviour is a rogue agent from day one; the fingerprint and the sweep can notice some of it, and only for triggers that were tried"),
 ("C20", "N600", "R12", "PARTIAL", "the bill records source, revision, lineage and the supplier's own data statement; none of those is verified by Ledgerly"),
 ("C20", "N600", "R09", "PARTIAL", "covers load-time code execution and tampering in transit; it does not cover model theft, inference attacks or extraction"),
 ("C20", "I42K", "A.7.5", "EVIDENCE_FOR", "the bill's data statement and lineage fields are records of provenance as the supplier gave it; Ledgerly's own training data for the triage model is recorded by digest only"),
 ("C20", "I42K", "A.10.3", "EVIDENCE_FOR", "the bill is the supplier record for a model; the supplier assessment itself is a person's work outside the control"),
 ("C20", "I42K", "A.7.3", "PARTIAL", "the acquisition of data for the triage model is recorded; no acquisition process for a vendor's training data exists to record"),
 ("C20", "I42K", "A.6.2.4", "PARTIAL", "behaviour evidence is attached to the bill by digest; it is the Chapter 18 gate's suite, which does not look for hidden behaviours"),
 ("C20", "EUAI", "Art15", "ALIGNED_WITH", "Art 15(5) lists measures against attempts to manipulate the training data set (data poisoning) and pre-trained components (model poisoning); applies from 2027-12-02 to high-risk systems [VERIFY]"),
]
def rows40(edition_override: dict | None = None) -> list[Row]:
    e = dict(EDN); e.update(edition_override or {})
    return rows38(edition_override) + [Row(c, s, i, e[s], rel, lim, CAT.items[f"{s}:{i}"].title if f"{s}:{i}" in CAT.items else "") for c, s, i, rel, lim in _ROWS40]
# Items the author considered and judged out of scope for an invoice-and-email agent, with the reason (a row with relation NA).
_NA = [("N600", "R01", "no chemical, biological, radiological or nuclear content is produced or enabled by an invoice agent"), ("N600", "R03", "Quill does not generate public content"), ("N600", "R05", "environmental impact of model use is out of scope of the control set"),
       ("N600", "R06", "no decision about people is made by Quill"), ("N600", "R10", "no content is published"), ("N600", "R11", "no content is published"), ("N600", "R08", "Quill does not publish information"),
       ("LLM25", "LLM09", "covered in part by C02 under N600:R02; no separate control")]
def na_rows() -> list[Row]:
    return [Row("-", s, i, EDN[s], "NA", "", CAT.items[f"{s}:{i}"].title, reason) for s, i, reason in _NA]

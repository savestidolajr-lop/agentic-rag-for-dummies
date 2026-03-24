/** Port of Python _auto_highlight from gradio_app.py */

const CODE_SPLIT_RE = /(`{3}[\s\S]*?`{3}|`[^`\n]+`)/g

// Case names: Smith v Jones [2020] HCA 15
const CASE_RE = /(?<!\*)((?:[A-Z][A-Za-z&',.]*(?:\s+[A-Za-z&',.]+)*)\s+v\s+(?:[A-Z][A-Za-z&',.]*(?:\s+[A-Za-z&',.]+)*)\s*\[\d{4}\][^\n]*?)(?!\*)/g

// Legislation: Residential Tenancies Act 2010
const ACT_RE = /(?<!\*)((?:[A-Z][a-zA-Z]+(?:\s+[A-Za-z]+)*)\s+(?:Act|Regulation|Rules|Code|Ordinance)\s+\d{4})(?!\*)/g

// Dollar amounts: $1,000 / $1.5 million
const AMOUNT_RE = /(?<!\*)(\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?)(?!\*)/gi

// Dates: 1 January 2024
const DATE_RE = /(?<!\*)(\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b)(?!\*)/gi

// Section references: s 42(1)(a), ss 3-5, section 5, cl 3, Part IV, Schedule 1
const SECTION_RE = /(?<!\*)(\b(?:ss?|cl(?:ause)?|section|Part|Schedule|reg(?:ulation)?)\s+\d+[A-Za-z]?(?:\([^)]{1,10}\))*(?:\s*[-–]\s*\d+[A-Za-z]?)?)(?!\*)/g

export function autoHighlight(text: string): string {
  const segments = text.split(CODE_SPLIT_RE)
  const out: string[] = []

  segments.forEach((seg, i) => {
    if (i % 2 === 1) {
      // Code block — pass through unchanged
      out.push(seg)
      return
    }
    seg = seg.replace(CASE_RE, '**$1**')
    seg = seg.replace(ACT_RE, '**$1**')
    seg = seg.replace(AMOUNT_RE, '**$1**')
    seg = seg.replace(DATE_RE, '**$1**')
    seg = seg.replace(SECTION_RE, '**$1**')
    out.push(seg)
  })

  return out.join('')
}

/** Strip [CITED_DOCUMENTS] and [OPTIONS:] tags from text */
export function stripTags(text: string): string {
  return text
    .replace(/\[CITED_DOCUMENTS\][\s\S]*?\[\/CITED_DOCUMENTS\]/gi, '')
    .replace(/\[OPTIONS:[^\]]*\]/gi, '')
    .trim()
}

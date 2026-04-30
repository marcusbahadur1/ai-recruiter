/**
 * Mock job descriptions used across the AI Chat test suite.
 *
 * All hiring_manager_email values use marcus@aiworkerz.com so that
 * hiring-manager notification emails land in the test inbox.
 * Outreach emails go to real candidates unless EMAIL_TEST_MODE is on
 * in Super Admin → Platform Keys.
 */

export const JD_T01_JAVA_DEVELOPER = `
I need to hire a Senior Java Developer. Here are all the details:

Role: Senior Java Developer
Location: Sydney CBD, hybrid 3 days per week in office
Experience: 5+ years with Java and Spring Boot
Salary: AUD $160,000 – $200,000 per year
Required skills: Java, Spring Boot, Microservices, PostgreSQL, Kafka
Tech stack: Java 17, Spring Boot 3, PostgreSQL, Kafka, Docker, AWS EKS
Team size: 8 engineers
Hiring manager: Marcus Bahadur, marcus@aiworkerz.com
Minimum suitability score: 7
Candidate target: 15
Number of test questions: 5
Interview format: text
`.trim()

export const EXPECTED_TITLE_T01 = 'Java'

// ── T02 — Marketing Manager, missing hiring manager ───────────────────────────
export const JD_T02_MARKETING_MANAGER = `
We're looking for a Marketing Manager to lead our demand generation and content team.

Location: London, UK — hybrid 2 days in office per week
Experience: 4+ years B2B SaaS marketing
Required skills: Content Strategy, HubSpot, Google Analytics, LinkedIn Ads, SEO
Salary: GBP £65,000 – £80,000 per year
Team of 4 reports to this role.
`.trim()

// hiring_manager_name and hiring_manager_email intentionally missing from above
export const T02_FOLLOWUP_HM = 'Marcus Bahadur, marcus@aiworkerz.com'

export const EXPECTED_TITLE_T02 = 'Marketing'

// ── T03 — Data Scientist, manual conversational flow ─────────────────────────
export const OPENING_T03 = `I need to find a data scientist, someone experienced with Python and machine learning`

// answers for each manual step in T03
export const T03_ANSWERS = {
  roleBasics:  'Data Scientist. Skills: Python, scikit-learn, TensorFlow, SQL, Spark. 4+ years experience.',
  location:    'Melbourne, Australia. Hybrid 3 days in office. Salary AUD $130k–$160k.',
  hiring:      'Hiring manager: Marcus Bahadur, marcus@aiworkerz.com. Min score 7. Target 20 candidates. Team size 5.',
  assessment:  'Use default outreach. Default evaluation is fine. 5 test questions. Text format.',
}

export const EXPECTED_TITLE_T03 = 'Data Scientist'

// ── T07 — Remote global React Developer ───────────────────────────────────────
export const JD_T07_REACT_REMOTE = `
Senior React Developer — fully remote, open to candidates anywhere in the world.

5+ years of React experience. Must be strong in TypeScript, Next.js, Redux Toolkit,
REST APIs, and GraphQL. Nice to have: testing with Jest + Cypress, CI/CD experience.
Salary: USD $100,000 – $130,000 per year.
Team of 6 frontend engineers working across 4 time zones.
Hiring manager: Marcus Bahadur (marcus@aiworkerz.com).
Minimum suitability score: 6. Target 20 candidates. Text interview format.
`.trim()

export const EXPECTED_TITLE_T07 = 'React'

// ── T08 — CFO, non-tech executive role ────────────────────────────────────────
export const JD_T08_CFO = `
We are searching for a Chief Financial Officer to join our ASX-listed company in Sydney.

The CFO will be responsible for all financial operations, reporting to the Board and CEO.
Key responsibilities: financial reporting, capital allocation, M&A advisory, investor
relations, IFRS compliance, ASX continuous disclosure obligations.
Minimum 10+ years in senior finance, at least 3 as CFO or VP Finance.
CPA or CA qualified. MBA preferred but not essential.
Must be onsite in Sydney CBD 5 days per week.
Total compensation package AUD $350,000 – $450,000.
Direct team of 12 finance professionals.
Hiring manager: Marcus Bahadur, marcus@aiworkerz.com.
Minimum suitability score: 8. Target 10 candidates.
`.trim()

export const EXPECTED_TITLE_T08 = 'Financial Officer'

// ── T09 — Minimal info ─────────────────────────────────────────────────────────
export const OPENING_T09 = `I need a developer`

// Generic answers to AI follow-up questions in T09
export const T09_FOLLOWUPS = [
  'Backend developer, Python preferred',
  'Sydney, hybrid. Salary around $120k–$150k',
  'Marcus Bahadur, marcus@aiworkerz.com. Min score 6. 20 candidates.',
  'Default outreach and evaluation are fine. 5 questions. Text format.',
]

export const EXPECTED_TITLE_T09 = 'Developer'

// ── T10 — Conflicting info ────────────────────────────────────────────────────
export const JD_T10_CONFLICTING = `
Frontend Developer — must work onsite in both Melbourne AND Sydney simultaneously
(candidate must commute between both offices as required).
Salary is either $80,000 per year OR equity-only compensation, depending on experience.
Requires 2 years of experience but will lead a team of 15 senior engineers and architects.
Hiring manager: Marcus Bahadur, marcus@aiworkerz.com.
`.trim()

export const EXPECTED_TITLE_T10 = 'Frontend'

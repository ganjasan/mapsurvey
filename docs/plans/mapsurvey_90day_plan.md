# Mapsurvey: Тактический план первых 90 дней

## Общая структура запуска

**Week 1-4**: Pre-launch подготовка  
**Week 5-8**: Public launch + community building  
**Week 9-12**: First customers + product iteration  

**Ключевая метрика успеха 90 дней**: 50 self-hosted инсталляций + 500 GitHub stars + 5 beta customers для cloud

---

## WEEK 1: Foundation Setup

### День 1-2: GitHub & Infrastructure
- [X] Создать GitHub organization `mapsurvey`
- [X] Setup repositories (core, web-client, mobile, docs, deployment)
- [X] Настроить branch protection, CI/CD (GitHub Actions)
- [X] Создать initial README с vision statement
- [X] Добавить LICENSE файлы (AGPLv3 для core, MIT для mobile)
- [X] Setup Discord/Slack community server (пока приватный)

**Ответственный**: CTO  
**Output**: Работающая GitHub инфраструктура

### День 3-4: Website & Landing Page
- [x] Купить домен mapsurvey.org
- [X] Создать минималистичный landing page:
  - Hero: "Open Source PPGIS for Modern Teams"
  - 3 key benefits vs Maptionnaire (table)
  - GitHub star button
  - Email signup для early access
  - Roadmap preview
- [ ] Setup analytics (Plausible/Simple Analytics - privacy-focused)
- [ ] Setup email (PostMark/SendGrid) для transactional emails

**Ответственный**: CEO + Engineer  
**Output**: Live website с email capture

### День 5: Documentation Foundation
- [ ] Setup MkDocs с Material theme
- [ ] Написать Quick Start guide (Docker Compose installation)
- [ ] Создать Architecture overview (системная диаграмма)
- [ ] Setup docs.mapsurvey.org hosting

**Ответственный**: CTO  
**Output**: Базовая документация для contributors

---

## WEEK 2: Content & Messaging

### День 1-2: Core Messaging
- [ ] Написать "Why we're building Mapsurvey in the open" blog post
- [ ] Создать comparison page: Mapsurvey vs Maptionnaire vs Social Pinpoint
- [ ] Подготовить 5 canned answers для FAQ
- [ ] Написать elevator pitch (30 sec, 1 min, 5 min versions)

**Ответственный**: CEO  
**Output**: Messaging deck

### День 3-4: Launch Content Calendar
- [ ] Спланировать 30 дней контента post-launch:
  - Week 1: Technical deep-dives (architecture)
  - Week 2: Comparison content (vs competitors)
  - Week 3: Use case tutorials
  - Week 4: Community spotlights
- [ ] Написать 10 постов для LinkedIn (CEO личный аккаунт)
- [ ] Подготовить Product Hunt launch description + gallery

**Ответственный**: CEO  
**Output**: Content buffer на месяц

### День 5: Community Guidelines
- [ ] Написать CONTRIBUTING.md
- [ ] Создать Code of Conduct
- [ ] Подготовить issue templates (bug, feature request, question)
- [ ] Создать 20 "good first issue" для contributors
- [ ] Setup GitHub Discussions

**Ответственный**: CTO  
**Output**: Contributor-friendly репозиторий

---

## WEEK 3: Pre-Launch Outreach

### День 1-2: Target List Building
- [ ] Составить список 100 потенциальных early adopters:
  - 30 университетов с urban planning programs
  - 30 консалтинговых компаний (LinkedIn search)
  - 20 civic tech сообществ
  - 20 open source GIS contributors
- [ ] Найти email адреса (Hunter.io, LinkedIn)
- [ ] Сегментировать по персоне

**Ответственный**: CEO  
**Output**: CRM setup с 100 leads

### День 3-4: Personal Outreach (Warm)
- [ ] Написать 20 персонализированных emails знакомым в GIS/civic tech:
  - "Мы запускаем open source PPGIS, хотели бы ваш feedback"
  - Попросить early access signup
  - Спросить, можно ли анонсировать в их community
- [ ] Outreach в 5 Slack/Discord communities где вы участник:
  - r/gis Discord
  - Civic Tech Slack
  - Open Source GIS groups

**Ответственный**: CEO + CTO  
**Output**: 20 warm leads в pipeline

### День 5: Beta Tester Recruitment
- [ ] Создать "Join Beta" форму (Typeform/Tally)
- [ ] Написать email sequence для beta applicants:
  - Email 1: Confirmation + What to expect
  - Email 2 (1 week): Early access link
  - Email 3 (2 weeks): First survey tips
- [ ] Setup beta.mapsurvey.io subdomain

**Ответственный**: Engineer  
**Output**: Beta program infrastructure

---

## WEEK 4: Final Pre-Launch Polish

### День 1-2: MVP Feature Freeze
- [ ] Code freeze для launch версии
- [ ] QA testing основных flows:
  - Account creation
  - Project setup
  - Survey publishing
  - Data export
- [ ] Bug triage (P0 must fix, P1 can ship)
- [ ] Performance testing (1000 responses load test)

**Ответственный**: CTO + Engineer  
**Output**: Stable MVP

### День 3: Launch Assets
- [ ] Создать demo video (3 min screencast):
  - 0-30s: Problem statement
  - 30s-2min: Product walkthrough
  - 2-3min: Call to action
- [ ] Screenshot gallery (10 images):
  - Map editor
  - Survey builder
  - Analytics dashboard
  - Mobile app mockups
- [ ] Social media assets (Twitter/LinkedIn graphics)

**Ответственный**: CEO  
**Output**: Marketing collateral

### День 4: Press & Influencer List
- [ ] Составить список 30 journalists/bloggers:
  - GovTech reporters
  - Open source publications (The New Stack, InfoWorld)
  - GIS media (Geospatial World, Directions Magazine)
- [ ] Написать press release draft
- [ ] Outreach к 10 micro-influencers в GIS/civic tech:
  - Попросить pre-launch access для review

**Ответственный**: CEO  
**Output**: PR outreach list

### День 5: Launch Dry Run
- [ ] Rehearsal Product Hunt submission
- [ ] Test всех signup flows
- [ ] Проверить email notifications
- [ ] Убедиться, что docs/website/repo синхронизированы
- [ ] Final team sync: launch checklist review

**Ответственный**: Вся команда  
**Output**: Go/No-Go decision

---

## WEEK 5: PUBLIC LAUNCH 🚀

### День 1 (Monday): Soft Launch
**6:00 AM PT** — Product Hunt submission
- [ ] Submit на Product Hunt (maker: CEO)
- [ ] Respond to every comment первые 24 часа
- [ ] Upvote coordination (НЕ fake, только genuine supporters)

**9:00 AM PT** — Hacker News
- [ ] Post "Show HN: Mapsurvey – Open Source PPGIS Platform"
- [ ] Monitor comments, respond быстро

**12:00 PM PT** — Reddit
- [ ] r/opensource: "We're open-sourcing our PPGIS platform"
- [ ] r/gis: "Show and Tell: New open source PPGIS tool"
- [ ] r/urbanplanning: (подождать community reaction прежде чем постить)

**3:00 PM PT** — Social Media
- [ ] LinkedIn post (CEO personal): Long-form story
- [ ] Twitter thread (company account): 10-tweet thread о why open source
- [ ] Tag relevant people/orgs в GIS community

**Ответственный**: CEO (orchestration), CTO (tech questions)  
**Метрика дня**: 200+ GitHub stars, 50+ email signups

### День 2-3: Community Engagement
- [ ] Respond to all GitHub issues/questions (target <2 hour response)
- [ ] Welcome every new contributor в Discussions
- [ ] Thank everyone who starred на Twitter
- [ ] Post launch results на LinkedIn: "48 hours in: X stars, Y downloads"
- [ ] Outreach к людям из pre-launch списка: "We launched!"

**Ответственный**: CTO + CEO  
**Метрика**: 300+ stars, 10+ self-hosted attempts

### День 4-5: Press Follow-Up
- [ ] Send press release к 30 journalists из списка
- [ ] Personalized pitch топ-10 приоритетам:
  - "Thought you'd find this interesting given your [article]..."
- [ ] Post на GIS forums (GeoNet, QGIS community)
- [ ] Reach out к podcast hosts (3-5 pitches)

**Ответственный**: CEO  
**Метрика**: 1-2 media mentions

---

## WEEK 6-7: Community Building

### Week 6 Focus: Developer Relations

**Monday**: 
- [ ] First Community Call (Zoom, 30 min)
  - Introduction to project
  - Roadmap discussion
  - Q&A
  - Record & post на YouTube

**Tuesday-Wednesday**:
- [ ] Create 5 tutorial blog posts:
  - "Your First Mapsurvey Project in 10 Minutes"
  - "Self-Hosting Mapsurvey with Docker"
  - "Migrating from Maptionnaire: Step-by-Step"
  - "Building Custom Map Layers"
  - "Analyzing PPGIS Data with Python"

**Thursday-Friday**:
- [ ] Review and merge 10 pull requests
- [ ] Create 10 new "good first issue" tasks
- [ ] Reach out персонально к 5 contributors: Thank you + что дальше?

**Метрика недели**: 5 merged PRs from external contributors

### Week 7 Focus: Customer Development

**Monday-Tuesday**:
- [ ] Schedule 15 customer development интервью:
  - 5 self-hosted users
  - 5 potential cloud customers
  - 5 competitive users (Maptionnaire/Social Pinpoint)
- [ ] Подготовить interview guide (Jobs-to-be-Done framework)

**Wednesday-Friday**:
- [ ] Conduct 10 интервью (zoom, 30 min each)
- [ ] Записать insights в Notion/Airtable
- [ ] Identify top 3 feature requests
- [ ] Identify top 3 blockers to adoption

**Метрика недели**: 10 completed interviews, insights doc

---

## WEEK 8: Beta Cloud Launch

### Pre-Beta Checklist
- [ ] Cloud infrastructure готова (AWS/GCP setup)
- [ ] Payment integration (Stripe) работает
- [ ] Email onboarding sequence готова (5 emails)
- [ ] In-app tutorials/tooltips добавлены
- [ ] Support system готов (Intercom/Plain)

### Monday: Invite First 10 Beta Users
- [ ] Персональные emails с beta access link
- [ ] Onboarding call с каждым (30 min)
- [ ] Ask: "What's your first project you want to create?"

### Tuesday-Friday: Feedback Loop
- [ ] Daily check-ins с beta users
- [ ] Fix critical bugs в течение 24 часов
- [ ] Ship 1-2 small improvements на основе feedback
- [ ] Document всё в changelog

**Метрика недели**: 10 beta users, 5 created projects, 3 published surveys

---

## WEEK 9-10: First Paid Customers

### Week 9: Sales Outreach (Consultancies)

**Target**: 50 консалтинговых компаний из списка

**Monday**: Email Campaign Setup
- [ ] Сегментировать список (по размеру, гео, expertise)
- [ ] Написать 3 варианта cold email:
  - Вариант A: Cost savings angle
  - Вариант B: Open source flexibility angle
  - Вариант C: White-label branding angle
- [ ] Setup email tracking (Mailtrack/Streak)

**Tuesday-Thursday**: Outreach (20 emails/день)
- [ ] Personalize каждый email (mention их проект/клиента)
- [ ] Follow-up через 3 дня если no response
- [ ] Track opens, replies, bounces

**Friday**: 
- [ ] Review результаты A/B/C variants
- [ ] Schedule demos с interested leads
- [ ] Update messaging на основе responses

**Метрика недели**: 10 demo requests

### Week 10: Converting Demos to Customers

**Monday-Wednesday**: Conduct Demos (5-10 demos)
- [ ] 30-minute demo format:
  - 5 min: Their use case discussion
  - 15 min: Live product demo
  - 5 min: Pricing & next steps
  - 5 min: Q&A
- [ ] Send follow-up email с recording + trial link

**Thursday-Friday**: Close First Deals
- [ ] Follow-up calls с hot leads
- [ ] Offer "Founding Customer" discount (50% off Year 1)
- [ ] Условие: Testimonial + case study участие
- [ ] Send contracts (DocuSign)

**Метрика недели**: 3-5 signed customers, $500-1000 MRR

---

## WEEK 11-12: Product Iteration & Scale Prep

### Week 11: Feature Sprint (based on feedback)

**Monday**: Prioritization
- [ ] Review all feedback from beta + customers
- [ ] Rank features by Impact/Effort
- [ ] Pick top 3 for 2-week sprint

**Tuesday-Friday**: Development
- [ ] Ship top 3 features
- [ ] Write docs для new features
- [ ] Notify users в email update

**Метрика недели**: 3 new features shipped

### Week 12: Content & Authority Building

**Monday-Tuesday**: Case Study #1
- [ ] Interview с first customer
- [ ] Write 1000-word case study:
  - Challenge
  - Solution
  - Results (with metrics)
- [ ] Get approval, publish на blog
- [ ] Promote на LinkedIn, Twitter, Reddit

**Wednesday**: Academic Outreach
- [ ] Email 20 университетов из списка
- [ ] Offer free academic licenses
- [ ] Propose collaboration на research paper

**Thursday-Friday**: Conference Submissions
- [ ] Submit speaking proposals:
  - State of the Map (OSM conference)
  - FOSS4G (open source GIS)
  - APA National Conference
- [ ] Topic: "Open Source PPGIS: Lessons from First 90 Days"

**Метрика недели**: 1 case study published, 3 conference submissions

---

## KEY METRICS: 90-Day Scorecard

### GitHub & Open Source
- [ ] Stars: 500+ (success), 300-500 (ok), <300 (needs work)
- [ ] Contributors: 10+ external
- [ ] Forks: 50+
- [ ] Self-hosted deployments: 50+ tracked

### Cloud Business
- [ ] Beta users: 20+
- [ ] Paid customers: 5+ 
- [ ] MRR: $500-1000
- [ ] Trial signups: 50+
- [ ] Trial-to-paid conversion: 20%+

### Community & Marketing
- [ ] Website visitors: 5,000+/месяц
- [ ] Email list: 500+
- [ ] LinkedIn followers: 200+
- [ ] Blog posts published: 15+
- [ ] Media mentions: 3+

### Customer Success
- [ ] Customer interviews completed: 20+
- [ ] NPS score: 40+ (early adopters)
- [ ] Churn: 0% (too early)
- [ ] Active projects created: 30+

---

## CONTINGENCY PLANS

### If GitHub Stars < 200 by Week 8
**Причина**: Недостаточная видимость или value proposition  
**Action**:
- Re-launch на Product Hunt (v2.0 с major feature)
- Aggressive DevRel: contribute to related projects, cross-promote
- Paid promotion: sponsor newsletters (Console, TLDR)

### If Zero Paid Customers by Week 10
**Причина**: Pricing, features, или positioning  
**Action**:
- Extend beta period, gather more feedback
- Pivot pricing: introduce $29/mo micro plan
- Offer consulting services для revenue

### If Self-Hosted Adoption Low
**Причина**: Installation сложность  
**Action**:
- Create 1-click installers (Heroku button, DigitalOcean 1-click)
- Video tutorials series
- Managed installation service ($200 one-time)

---

## WEEKLY RITUALS (для sustainability)

### Monday (Planning Day)
- 9:00 AM: Team standup — week priorities
- 10:00 AM: Review metrics dashboard
- 11:00 AM: Customer/community feedback review
- **Output**: Weekly goal sheet

### Tuesday-Thursday (Execution Days)
- Daily standup: 15 min
- Focus time blocks: 4-hour deep work
- End-of-day: Slack update на progress

### Friday (Shipping Day)
- Ship something every Friday (feature, blog post, update)
- 3:00 PM: Team retro — what worked, what didn't
- 4:00 PM: Plan next week
- **Output**: Public changelog update

### Continuous (Daily)
- GitHub issue triage: <2 hour response time
- Community engagement: 30 min/день на Discord/forums
- Content: 1 social media post/день minimum

---

## TOOLS & STACK (рекомендованные)

### Development
- **GitHub** — code, issues, discussions
- **Linear** — internal task management
- **Vercel/Netlify** — website hosting
- **AWS/Railway** — cloud infrastructure

### Marketing & Sales
- **Plausible** — privacy-first analytics
- **ConvertKit/Loops** — email marketing
- **Cal.com** — demo scheduling
- **Stripe** — payments

### Community
- **Discord** — community chat
- **MkDocs Material** — documentation
- **YouTube** — video tutorials, community calls

### Customer Success
- **Plain/Intercom** — support chat
- **Notion** — knowledge base, CRM (early stage)
- **Loom** — video responses

---

## SUCCESS DEFINITION (90 дней)

**Minimum Viable Success**:
- 300+ GitHub stars
- 30+ self-hosted deployments
- 3+ paying customers ($300+ MRR)
- 10+ external contributors
- 1 media mention

**Strong Success**:
- 500+ GitHub stars
- 50+ self-hosted deployments
- 10+ paying customers ($1,000+ MRR)
- 25+ external contributors
- 5+ media mentions
- 1 partnership signed

**Exceptional Success**:
- 1,000+ GitHub stars
- 100+ self-hosted deployments
- 20+ paying customers ($2,000+ MRR)
- 50+ external contributors
- 10+ media mentions
- 3+ partnerships
- Conference speaking slot confirmed

---

## TEAM WEEKLY TIME ALLOCATION

### CEO (50h/week)
- Sales & Partnerships: 20h
- Content & Marketing: 15h
- Customer Interviews: 10h
- Strategy & Planning: 5h

### CTO (50h/week)
- Code & Architecture: 25h
- Community Management: 15h
- Technical Writing: 5h
- Hiring & Mentoring: 5h

### Engineer (40h/week)
- Feature Development: 30h
- Bug Fixes & Support: 5h
- Documentation: 5h

---

**Последнее напоминание**: Не пытайтесь сделать всё идеально. Запускайте быстро, слушайте feedback, итерируйте. Open source дает вам право на ошибки — community поможет исправить.

**Удачи с запуском! 🚀**

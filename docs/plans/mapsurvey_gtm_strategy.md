# GTM Стратегия Mapsurvey: Open Source Core + Paid Cloud

## Executive Summary

**Модель монетизации**: Open Core с облачным SaaS
**Время до первых платящих клиентов**: 6 месяцев
**Целевой ARR Year 1**: $150,000-250,000
**Основная гипотеза**: Прозрачность, мобильность и доступность побеждают закрытые премиум-решения в растущем рынке civic tech

---

## 1. СТРАТЕГИЧЕСКОЕ ПОЗИЦИОНИРОВАНИЕ

### 1.1 Центральная позиция рынка

**"Первая по-настоящему открытая PPGIS платформа для современных команд"**

Три столпа позиционирования:
- **Open by Default** — весь код доступен, нет vendor lock-in
- **Mobile-First** — нативные приложения для полевой работы
- **Transparent Always** — открытые цены, публичная roadmap, community-driven развитие

### 1.2 Дифференциация от Maptionnaire

| Параметр | Maptionnaire | Mapsurvey (наша позиция) |
|----------|--------------|-------------------------|
| Код | Проприетарный | Open Source (AGPLv3/MIT) |
| Цены | Скрытые | Публичные на сайте |
| Вход | €2,900+/год | Free self-hosted / $49/мес cloud |
| Мобильность | Только веб | Native iOS/Android apps |
| Trial | По запросу sandbox | 14 дней full-featured cloud |
| Картография | Без Google Maps | Google + OSM + Mapbox |
| Поддержка | Email | Community forum + premium support |

### 1.3 Целевое сообщение (Messaging Framework)

**Для городских планировщиков**: "Соберите качественные пространственные данные от жителей без зависимости от дорогих проприетарных платформ"

**Для консультантов**: "Предложите клиентам передовую PPGIS-платформу с вашим брендингом и полным контролем данных"

**Для исследователей**: "Воспроизводимая методология сбора геоданных с открытым кодом для научной валидации"

**Для некоммерческих организаций**: "Вовлекайте сообщества в принятие решений с бесплатным self-hosted решением"

---

## 2. СЕГМЕНТАЦИЯ И ТАРГЕТИНГ

### 2.1 Primary Targets (70% усилий)

#### Сегмент A: Консалтинговые компании в urban planning (40%)
- **Профиль**: 5-50 человек, делают 10-50 проектов/год для муниципалитетов
- **Pain points**: 
  - Высокие затраты на Maptionnaire ($15,000-40,000/год)
  - Нужен white-label для брендинга
  - Хотят кастомизацию под специфику проекта
- **Покупатель**: GIS Lead / Project Manager
- **Каналы**: LinkedIn, отраслевые конференции (APA, ISOCARP), direct outreach
- **Конверсия**: Self-hosted trial → Cloud при масштабировании → Enterprise plan

#### Сегмент B: Средние города (100k-500k население) (30%)
- **Профиль**: Города в США, Европе, Австралии с active civic engagement программами
- **Pain points**:
  - Бюджетные ограничения госсектора
  - Требования к GDPR/accessibility/security
  - Нет IT-ресурсов для self-hosting
- **Покупатель**: Chief Innovation Officer / Community Engagement Manager
- **Каналы**: Government tech publications, National League of Cities, Smart Cities events
- **Конверсия**: Free tier → Professional по мере роста проектов

### 2.2 Secondary Targets (30% усилий)

#### Сегмент C: Исследовательские университеты
- **Мотивация**: Открытый код для воспроизводимости, академические лицензии
- **Монетизация**: Academic cloud tier ($199/год) + citations + talent pipeline

#### Сегмент D: НКО и community organizations
- **Мотивация**: Бесплатный self-hosted для grassroots проектов
- **Монетизация**: Freemium → Paid при институционализации + evangelist-эффект

---

## 3. PRICING СТРАТЕГИЯ

### 3.1 Self-Hosted (Free Forever)

**Что включено**:
- Полный функционал платформы (core features)
- Community forum support
- Docker Compose для быстрого развёртывания
- Документация и видео-гайды

**Что не включено**:
- Managed hosting
- SLA и priority support
- Advanced features (AI analysis, SSO, audit logs)
- White-label брендирование

**Цель**: 5,000 self-hosted инсталляций к концу Year 1

### 3.2 Cloud SaaS Tiers

#### STARTER ($49/месяц или $490/год)
- 3 активных проекта
- 5,000 ответов/месяц
- Mobile apps доступ
- Email support (48h response)
- Community branding
- 10GB storage
- **Target**: Малые консалтинги, пилотные проекты городов

#### PROFESSIONAL ($199/месяц или $1,990/год)
- 15 активных проектов
- 25,000 ответов/месяц
- Priority support (24h response)
- Custom branding
- AI sentiment analysis
- 100GB storage
- 5 team seats
- **Target**: Средние консалтинги, активные города

#### BUSINESS ($499/месяц или $4,990/год)
- Unlimited проекты
- 100,000 ответов/месяц
- SSO (SAML)
- Dedicated support manager
- White-label полностью
- API access (10k calls/month)
- 500GB storage
- 20 team seats
- **Target**: Крупные консалтинги, большие города

#### ENTERPRISE (custom pricing, от $1,500/месяц)
- Все из Business +
- On-premise deployment опция
- Custom SLA (99.9%+)
- ArcGIS real-time streaming
- Dedicated infrastructure
- Unlimited API
- Security audit support
- **Target**: Государственные агентства, федеральный уровень

### 3.3 Add-ons (доступны на всех платных планах)

- **Extra responses**: $50 за 10,000 ответов
- **Professional services**: Онбординг ($500), custom integration ($150/час)
- **Academic license**: 50% скидка на Professional/Business для .edu/.ac
- **Nonprofit discount**: 30% скидка для зарегистрированных НКО

### 3.4 Pricing Philosophy

1. **Публичная прозрачность** — все цены на сайте без "Contact Sales"
2. **Линейный рост** — понятная логика масштабирования
3. **Self-service first** — оплата картой онлайн до Enterprise
4. **Annual discount** — 20% скидка при годовой оплате
5. **No surprises** — прозрачные soft limits с warning за неделю

---

## 4. ОТКРЫТЫЙ КОД: СТРАТЕГИЯ И ТАКТИКА

### 4.1 Licensing Strategy

**Open Core модель**:
- **Core (AGPLv3)**: Вся функциональность сбора данных, базовая аналитика, map engine
- **Cloud Extensions (Proprietary)**: SSO, advanced AI, audit logs, real-time sync
- **Mobile Apps (MIT)**: Полностью открыты для максимального adoption

**Почему AGPLv3 для core**: Защита от cloud-провайдеров, которые могут хостить без контрибуций, но разрешает enterprise self-hosting.

### 4.2 GitHub Стратегия

#### Репозитории
- `mapsurvey/core` — Backend + API (Go/Python)
- `mapsurvey/web-client` — Web frontend (React/TypeScript)
- `mapsurvey/mobile` — React Native apps
- `mapsurvey/docs` — Документация (MkDocs)
- `mapsurvey/deployment` — Docker, Kubernetes, Terraform templates
- `mapsurvey/examples` — Примеры проектов и интеграций

#### Метрики успеха (GitHub)
- **Week 1**: 100 stars
- **Month 3**: 500 stars, 20 contributors
- **Month 6**: 1,500 stars, 50 contributors, 10 forks с pull requests
- **Year 1**: 5,000 stars, 150 contributors, featured в Awesome GIS lists

#### Community Building
- **Contribution guide** с easy first issues (label: "good first issue")
- **Monthly community calls** (запись на YouTube)
- **Contributor recognition** — Hall of Fame на сайте
- **Hacktoberfest participation** для всплеска контрибуций

### 4.3 Developer Relations

- **Technical blog** (2 поста/месяц): архитектурные решения, PPGIS методология, case studies
- **Open roadmap** на GitHub Projects — полная прозрачность планов
- **API-first design** — все функции доступны через REST/GraphQL API
- **SDK packages**: JavaScript, Python, R — для исследователей и аналитиков

---

## 5. КАНАЛЬНАЯ СТРАТЕГИЯ

### 5.1 Inbound Channels (60% бюджета)

#### Content Marketing
**SEO-фокус** (долгосрочная инвестиция):
- 100+ страниц документации (захват long-tail "how to...")
- Сравнительные статьи: "Mapsurvey vs Maptionnaire", "Best PPGIS tools 2026"
- Кейсы с measurable outcomes (% participation increase, time saved)

**Блог** (2-3 поста/неделю):
- Technical deep-dives (для developers)
- Methodology guides (для планировщиков)
- Community spotlights (для engagement)

**Целевые keywords** (пример):
- "open source PPGIS" (difficulty: low, volume: 200/mo)
- "community engagement software" (difficulty: medium, volume: 1,200/mo)
- "participatory mapping tools" (difficulty: low, volume: 300/mo)

#### Community-Led Growth
- **Reddit**: r/gis, r/urbanplanning — полезные ответы + subtle mentions
- **GIS Stack Exchange** — активность + link в профиле
- **LinkedIn articles** — CEO/CTO публикуют thought leadership
- **Podcast appearances** — Urban planning, civic tech, open source подкасты

#### Product-Led Growth
- **GitHub discoverability** — topics, awesome lists, trending
- **Interactive demo** — публичная инсталляция для тестирования
- **Template library** — готовые шаблоны для типичных use cases (parks survey, bike lanes, budget allocation)

### 5.2 Outbound Channels (25% бюджета)

#### Direct Outreach
**Консалтинги** (50 targeted companies/месяц):
- Персонализированное cold email через CEO/CTO
- Referral: "Мы заметили, что вы используете [Maptionnaire/Social Pinpoint] для [project]..."
- Offer: Custom demo + migration assistance

**Города** (20 cities/месяц):
- Список из анализа Maptionnaire клиентов
- Outreach через LinkedIn к Chief Innovation Officers
- Angle: Cost savings + transparency + vendor independence

#### Partnerships
- **GIS консалтинги** (10-15 партнёров Year 1): Они внедряют, мы даём revenue share (20%)
- **University labs** (5-10 партнёров): Они публикуют исследования, мы даём academic licenses
- **Civic tech ассоциации**: Code for America brigades, mySociety network

### 5.3 Paid Acquisition (15% бюджета)

**Не раньше Month 6** — только после PMF validation.

- **LinkedIn Ads**: Job title targeting (Urban Planner, GIS Analyst, Community Engagement Manager)
- **Google Ads**: Brand defense + high-intent keywords ("Maptionnaire alternative")
- **Conference sponsorships**: APA National, ESRI User Conference (booth + speaking slot)

---

## 6. LAUNCH ROADMAP (FIRST 12 MONTHS)

### Phase 1: Foundation (Months 1-3) — "Build in Public"

**Goals**: MVP готов, первые 50 self-hosted инсталляций, 500 GitHub stars

**Тактика**:
- **Week 1**: 
  - Публичный GitHub release с Docker Compose setup
  - Launch на Product Hunt, Hacker News, r/opensource
  - CEO LinkedIn пост "Why we're open-sourcing PPGIS"
  
- **Week 2-4**:
  - 10 blog posts (migration guides, architecture, comparison)
  - Outreach к 20 университетам с open source programs
  
- **Week 5-12**:
  - Bi-weekly community calls
  - Первые 5 customer development интервью с self-hosted пользователями
  - Beta testing облачной версии с 10 early adopters

**Метрики**:
- GitHub: 500 stars, 5 external contributors
- Website: 2,000 unique visitors/месяц
- Self-hosted: 50 активных инсталляций
- Email list: 300 подписчиков

### Phase 2: Cloud Launch (Months 4-6) — "Go-to-Market"

**Goals**: Cloud platform live, первые 20 платящих клиентов, $10k MRR

**Тактика**:
- **Month 4**:
  - Официальный launch облачной платформы
  - Press release → GovTech, Geospatial Media
  - Beta to GA — конвертировать 10 beta users в платящих
  
- **Month 5**:
  - First customer case study (с метриками)
  - Webinar series: "Migrating from Maptionnaire to Mapsurvey"
  - Первые 2 партнёрства с консалтингами
  
- **Month 6**:
  - Launch mobile apps на iOS/Android
  - Integration marketplace (ArcGIS, Tableau, Power BI connectors)
  - First conference speaking slot (APA или State of the Map)

**Метрики**:
- Paid customers: 20 (10 Starter, 7 Professional, 3 Business)
- MRR: $10,000
- Conversion self-hosted → cloud: 2%
- Cloud trial → paid: 25%

### Phase 3: Scale (Months 7-12) — "Revenue & Retention"

**Goals**: $100k ARR, 2 Enterprise deals, product-market fit validated

**Тактика**:
- **Month 7-9**:
  - Dedicated sales hire (AE with gov/GIS experience)
  - Enterprise sales cycle начинается (6-9 месяцев)
  - Customer success program для retention
  
- **Month 10-12**:
  - Second round of funding ($500k-1M) на основе traction
  - Expansion hiring: 2 engineers, 1 DevRel, 1 Customer Success
  - Geographic expansion (Europe focus → GDPR compliance)

**Метрики**:
- Paid customers: 80
- ARR: $100,000-150,000
- NRR (Net Revenue Retention): 110%+
- GitHub: 5,000 stars, 100 contributors

---

## 7. МЕТРИКИ УСПЕХА

### 7.1 North Star Metric

**Активные проекты с >100 ответами в месяц** — показывает реальное использование платформы для принятия решений.

### 7.2 KPI Framework

#### Acquisition
- **Website traffic**: 5k → 20k unique/месяц (Month 1 → 12)
- **Trial signups**: 50/месяц к Month 12
- **Self-hosted downloads**: 200/месяц к Month 12

#### Activation
- **Time to first project created**: <15 минут
- **Trial to first survey published**: <24 часа для 60% users
- **Self-hosted успешные инсталляции**: 70% от downloads

#### Revenue
- **MRR growth**: 20% month-over-month (Months 4-12)
- **ARR**: $150k к концу Year 1
- **ARPU (Average Revenue Per User)**: $150/месяц
- **CAC (Customer Acquisition Cost)**: <$500 для cloud

#### Retention
- **Logo retention**: 90%+ после Month 3
- **GRR (Gross Revenue Retention)**: 85%+
- **NRR (Net Revenue Retention)**: 110%+ (через upsells)

#### Engagement (Open Source)
- **GitHub stars growth**: 100/месяц к Month 12
- **Contributors**: 10 active/месяц
- **Community forum**: 50 weekly active users к Month 12

---

## 8. КОНКУРЕНТНАЯ ЗАЩИТА

### 8.1 Moats (рвы)

1. **Community moat**: Open source сообщество становится защитой — чем больше contributors, тем сложнее конкурировать
2. **Data network effects**: Публичные datasets и templates создают value
3. **Integration ecosystem**: Партнёрские интеграции (ArcGIS, Tableau и т.д.)
4. **Brand в academic**: Публикации с использованием Mapsurvey создают legitimacy

### 8.2 Competitive Response Plan

**Если Maptionnaire снизит цены**:
- Emphasize open source value (vendor independence, no lock-in)
- Публикуем case study о миграции с экономией

**Если появится новый open source конкурент**:
- Агрессивная community-engagement (быстрые merge PR, responsive issues)
- Feature velocity — релизы каждые 2 недели
- Partnership-driven differentiation

**Если ESRI запустит встроенное PPGIS**:
- Pivot к non-ESRI ecosystem (QGIS, Mapbox, Google)
- Emphasize neutrality и multi-platform

---

## 9. РИСКИ И МИТИГАЦИЯ

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Низкий adoption open source | Средняя | Высокое | Developer relations, showcase projects |
| Трудности монетизации freemium | Высокая | Высокое | Чёткое разделение free/paid, premium support |
| Недостаток enterprise features | Средняя | Среднее | Roadmap с SSO, audit logs в Q2 |
| Конкуренция с Maptionnaire | Низкая | Среднее | Дифференциация через mobile + transparency |
| Сложность self-hosting отпугивает | Высокая | Среднее | Managed onboarding service ($500) |
| Burn rate превышает revenue | Средняя | Критичное | Bootstrap-friendly: 3-4 человека команда Year 1 |

---

## 10. TEAM & BUDGET

### 10.1 Core Team (Year 1)

- **CEO/Co-founder** — GTM, fundraising, partnerships
- **CTO/Co-founder** — Product, architecture, community
- **Full-stack Engineer** — Features, cloud infrastructure
- **DevRel/Community Manager** (Part-time Month 6+) — GitHub, docs, developer advocacy

**Total headcount**: 3.5 FTE

### 10.2 Budget Allocation (Year 1: $250k)

- **Salaries**: $180k (72%)
- **Infrastructure**: $20k (AWS, domains, tools)
- **Marketing**: $30k (content, ads Month 6+, conferences)
- **Legal/Admin**: $10k (incorporation, contracts)
- **Reserve**: $10k

**Funding sources**:
- Bootstrapped: $50k (founders)
- Angel/Pre-seed: $200k
- Revenue Year 1: $100k (reinvested)

---

## 11. SUCCESS CRITERIA (12-месячная отметка)

### Must-Have (критичные для Series A)
- ✅ ARR $150k+ с 80+ paying customers
- ✅ NRR 110%+ (доказательство retention + expansion)
- ✅ 2+ Enterprise deals signed
- ✅ 5,000+ GitHub stars, active community

### Nice-to-Have (ускорители роста)
- 🎯 Featured в Gartner/Forrester отчётах по civic tech
- 🎯 Partnership с Code for America или аналогичной сетью
- 🎯 Academic paper published с Mapsurvey в methodology
- 🎯 10+ community-contributed integrations

### Leading Indicators (Month 6 checkpoint)
- ⚡ 50+ trial signups/месяц
- ⚡ 25%+ trial-to-paid conversion
- ⚡ <$500 CAC for cloud customers
- ⚡ Product-market fit score 40%+ (Sean Ellis test)

---

## ЗАКЛЮЧЕНИЕ

Эта GTM стратегия использует фундаментальную слабость закрытых PPGIS-платформ — отсутствие прозрачности и vendor lock-in. Open source создаёт trust и community moat, а облачная монетизация обеспечивает sustainable бизнес-модель.

**Ключевые принципы успеха**:
1. **Transparency beats opacity** — открытые цены, код, roadmap
2. **Community is the moat** — инвестиции в DevRel окупаются через network effects
3. **Mobile-first beats desktop-only** — полевая работа критична для PPGIS
4. **Freemium works in GovTech** — но требует чёткого value ladder

**Next Steps (Week 1)**:
1. Finalize MVP scope для open source release
2. Setup GitHub organization + initial repos
3. Write "Why we're open-sourcing PPGIS" announcement post
4. Identify 10 target customers для beta cloud access
5. Create 30-day content calendar для launch

# Better Cities Survey - Full Structure

## BLOCK 1: `intro` (Introduction and Anchor Point)

### Вопрос 1
- **name:** Welcome!
- **subtext:** `<p>This survey is conducted as part of the World Bank's <strong>'Better Cities'</strong> project to improve the quality of life in your city.</p><ul><li>Your answers are <strong>anonymous</strong></li><li>Used for planning purposes only</li><li>Takes 12-14 minutes</li></ul><p>Thank you for participating!</p>`
- **input_type:** html
- **required:** No

### Вопрос 2
- **name:** Where do you live?
- **subtext:** Mark your home or the nearest intersection on the map
- **input_type:** point
- **required:** Yes
- **icon_class:** fas fa-home
- **color:** #3388ff

---

## BLOCK 2: `everyday` (Everyday Geography)

### Вопрос 1
- **name:** Where do you work or study?
- **subtext:** Mark your primary place of work or study. If you work from home or are retired, skip this
- **input_type:** point
- **required:** No
- **icon_class:** fas fa-briefcase
- **color:** #ff7800

#### Под-вопросы для "Where do you work or study?"

**1)**
- **name:** Type
- **input_type:** choice
- **option_group:** work_study_type

**2)**
- **name:** Commute mode
- **input_type:** choice
- **option_group:** commute_mode

**3)**
- **name:** Commute time
- **input_type:** choice
- **option_group:** commute_time

---

### Вопрос 2
- **name:** Where do you spend your free time?
- **subtext:** Mark up to 3 places where you regularly meet friends, relax, or spend time outside home and work (cafes, parks, bazaars, libraries, gyms, courtyards)
- **input_type:** point
- **required:** No
- **icon_class:** fas fa-coffee
- **color:** #9c27b0

#### Под-вопросы для "Where do you spend your free time?"

**1)**
- **name:** Place type
- **input_type:** choice
- **option_group:** third_place_type

**2)**
- **name:** Frequency
- **input_type:** choice
- **option_group:** frequency

**3)**
- **name:** Why is this place important to you?
- **input_type:** text

---

## BLOCK 3: `climate_safety` (Climate Risks and Safety)

### Вопрос 1
- **name:** Where have you observed flooding, landslides, or mudflows?
- **subtext:** Mark locations of street flooding, landslides, or mudflows in the last 3 years. You can mark up to 3 locations.
- **input_type:** point
- **required:** No
- **icon_class:** fas fa-water
- **color:** #2196f3

#### Под-вопросы для "Where have you observed flooding..."

**1)**
- **name:** Event type
- **input_type:** choice
- **option_group:** hazard_type

**2)**
- **name:** When did it happen?
- **input_type:** text_line

**3)**
- **name:** Comment
- **input_type:** text

---

### Вопрос 2
- **name:** Where do you feel unsafe?
- **subtext:** Mark places you avoid due to feeling unsafe (poor lighting, crime, dangerous traffic, stray dogs). You can mark up to 3 locations.
- **input_type:** point
- **required:** No
- **icon_class:** fas fa-exclamation-triangle
- **color:** #f44336

#### Под-вопросы для "Where do you feel unsafe?"

**1)**
- **name:** Reason
- **input_type:** choice
- **option_group:** unsafe_reason

**2)**
- **name:** Time of day
- **input_type:** choice
- **option_group:** time_of_day

---

## BLOCK 4: `services` (Access to Services)

### Вопрос 1
- **name:** What important facilities are missing near your home?
- **subtext:** Mark locations where new facilities are needed. You can mark up to 3 locations.
- **input_type:** point
- **required:** No
- **icon_class:** fas fa-plus-circle
- **color:** #4caf50

#### Под-вопросы для "What important facilities are missing..."

**1)**
- **name:** Facility type
- **input_type:** choice
- **option_group:** missing_facility

---

### Вопрос 2
- **name:** Which park or green zone do you visit most often?
- **subtext:** Mark your favorite park or green space
- **input_type:** point
- **required:** No
- **icon_class:** fas fa-tree
- **color:** #8bc34a

#### Под-вопросы для "Which park or green zone..."

**1)**
- **name:** How often do you visit?
- **input_type:** choice
- **option_group:** frequency

---

## BLOCK 5: `infrastructure` (Infrastructure and Environment)

### Вопрос 1
- **name:** Mark road sections in poor condition
- **subtext:** Indicate broken roads, potholes, or lack of paving
- **input_type:** line
- **required:** No
- **icon_class:** fas fa-road
- **color:** #795548

#### Под-вопросы для "Mark road sections..."

**1)**
- **name:** Problem type
- **input_type:** choice
- **option_group:** road_problem

---

### Вопрос 2
- **name:** Water supply
- **subtext:** What is your primary source of water?
- **input_type:** choice
- **required:** No
- **option_group:** water_supply

### Вопрос 3
- **name:** Sewage
- **subtext:** What type of sewage system do you have?
- **input_type:** choice
- **required:** No
- **option_group:** sewage_type

---

## BLOCK 6: `ratings` (Service Quality Ratings)

### Вопрос 1
- **name:** Rate water supply quality
- **subtext:** If applicable
- **input_type:** rating
- **required:** No

### Вопрос 2
- **name:** How convenient is it to reach the nearest school/kindergarten?
- **input_type:** rating
- **required:** No

### Вопрос 3
- **name:** How convenient is it to reach a clinic/hospital?
- **input_type:** rating
- **required:** No

### Вопрос 4
- **name:** How do you rate public transport?
- **input_type:** rating
- **required:** No

### Вопрос 5
- **name:** Are there enough green zones in your neighborhood?
- **input_type:** choice
- **required:** No
- **option_group:** yes_no_4

---

## BLOCK 7: `demographics` (Demographics)

### Вопрос 1
- **name:** Age
- **input_type:** choice
- **required:** No
- **option_group:** age_group

### Вопрос 2
- **name:** Gender
- **input_type:** choice
- **required:** No
- **option_group:** gender

### Вопрос 3
- **name:** Housing type
- **input_type:** choice
- **required:** No
- **option_group:** housing_type

### Вопрос 4
- **name:** Additional Comments
- **subtext:** Is there anything else you would like to say about your city?
- **input_type:** text
- **required:** No

### Вопрос 5
- **name:** Consent for Personal Data Processing
- **subtext:** I give my voluntary consent to the processing of my personal data (including geolocation tags, demographic characteristics, and survey responses) to the following organizations: [Project Executor Name], World Bank, authorized research organizations. Purpose: Urban diagnostic and improvement recommendations for [City Name] under the 'Better Cities' project. Rights: I may withdraw consent, access my data, or request deletion at [email].
- **input_type:** choice
- **required:** Yes
- **option_group:** (создай отдельную группу `consent` с одним вариантом: 1: I agree)

---

## OptionGroups (для справки)

| Название | Варианты |
|----------|----------|
| work_study_type | 1: Work, 2: Study |
| commute_mode | 1: On foot, 2: Public transport, 3: Personal car, 4: Taxi, 5: Bicycle |
| commute_time | 1: Under 15 min, 2: 15-30 min, 3: 30-60 min, 4: Over an hour |
| third_place_type | 1: Cafe/Chaikhana, 2: Park, 3: Bazaar/Mall, 4: Library, 5: Gym, 6: Religious site, 7: Courtyard, 8: Riverside, 9: Other |
| frequency | 1: Daily, 2: Several times a week, 3: Weekly, 4: Several times a month, 5: Rarer |
| hazard_type | 1: Flooding, 2: Landslide, 3: Mudflow |
| unsafe_reason | 1: Poor lighting, 2: Crime, 3: Dangerous traffic, 4: Stray dogs, 5: Other |
| time_of_day | 1: Morning, 2: Daytime, 3: Evening, 4: Night, 5: Always |
| missing_facility | 1: School, 2: Kindergarten, 3: Clinic, 4: Pharmacy, 5: Grocery, 6: Park, 7: Transport stop, 8: Playground, 9: Other |
| road_problem | 1: Unpaved, 2: Potholes, 3: Broken pavement, 4: No sidewalk |
| water_supply | 1: Centralized 24/7, 2: Intermittent, 3: Public standpipe, 4: Delivered water, 5: Well/Borehole |
| sewage_type | 1: Centralized sewage, 2: Septic tank, 3: Cesspit, 4: None |
| likert_5 | 1: 1 - Very poor, 2: 2, 3: 3, 4: 4, 5: 5 - Excellent |
| yes_no_4 | 1: Yes, 2: Rather yes, 3: Rather no, 4: No |
| age_group | 1: 18-24, 2: 25-34, 3: 35-44, 4: 45-54, 5: 55-64, 6: 65+ |
| gender | 1: Male, 2: Female, 3: Prefer not to say |
| housing_type | 1: Old apartment, 2: New apartment, 3: Private house, 4: Dormitory |
| consent | 1: I agree |

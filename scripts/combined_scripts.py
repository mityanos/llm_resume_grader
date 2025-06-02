# Combined project files

# 001 - README.md

# LLM Resume Grader (A–D, Aviasales-style)

Автоматизация скрининга резюме и сопроводительных писем с помощью OpenAI API и кастомных чеклистов — для честного, масштабируемого и объяснимого первичного отбора кандидатов на ИТ-вакансии.

## 🟢 Как это работает — в двух словах

1. **Запусти** `python3 main.py`
2. **Скрипт автоматически найдёт все резюме** в папке `data/input/candidates/`
3. **Каждое резюме прогоняется через LLM (судью)** — нейросеть выставляет оценку (“A”, “B”, “C” или “D”) и пишет короткое объяснение
4. **Оценка переводится в число** (например, A=4, D=1 — см. config.yaml)
5. **Все кандидаты сортируются по рейтингу**
6. **Результаты сохраняются** в удобной таблице `results.md` (и в подробном JSON)

**Запустил — получил рейтинг кандидатов, готовый для быстрого отбора!**

---

## 🚀 Быстрый старт

```bash
# 1. Клонируй репозиторий
git clone https://github.com/mityanos/llm_resume_grader.git
cd llm_resume_grader

# 2. Виртуальное окружение (опционально)
python3 -m venv .venv
source .venv/bin/activate

# 3. Установи зависимости
pip install --upgrade pip
pip install -r requirements.txt

# 4. Добавь OpenAI API-ключ
cp .env.example .env
# открой .env и вставь свой ключ (получи на https://platform.openai.com/account/api-keys)

# 5. Положи резюме-кандидатов в папку data/input/candidates/
# форматы смотри ниже

# 6. **Запусти пайплайн**
python -m llm_resume_grader.main

# 7. Результаты будут в results.md и results.json
```

---

## 🗂 Структура репозитория

```
llm_resume_grader/
├── data/
│   ├── input/
│   │   └── candidates/    # папка для резюме (.md)
│   └── output/            # таблицы и артефакты
├── config.yaml            # параметры модели и pipeline
├── requirements.txt       # зависимости
├── system_prompt.md       # системный промт для LLM
├── main.py                # основной скрипт
├── .env.example           # шаблон для API-ключа
├── .gitignore             # игнорирует .env, результаты и артефакты
```

---

## ⚙️ Настройки и параметры

Вся конфигурация хранится в [`config.yaml`](sandbox:/mnt/data/config.yaml):

```yaml
llm:
  model: "gpt-4o-mini-2024-07-18"
  params:
    temperature: 0.2
    top_p: 1.0
    max_tokens: 1000
  retry_max: 6

grading:
  scale: {A: 4, B: 3, C: 2, D: 1}

paths:
  system_prompt: "system_prompt.md"
  candidates_glob: "candidates/*.md"
  out_md: "results.md"
  out_json: "results.json"
```

**Параметры OpenAI (`temperature`, `top_p`, `max_tokens`) регулируются прямо из YAML** и полностью пробрасываются в API вызовы.

---

## 📄 Формат резюме-кандидата (`candidates/*.md`)

Резюме должны быть в Markdown-формате.
**В начале файла (желательно!) указывай уникальный Candidate ID:**

```markdown
Candidate ID: C001
Name: Alex Swift

## Experience
- 8 yrs Backend Lead (FastAPI, PostgreSQL, AWS, Docker, Terraform)
- Drove 0-downtime migration to microservices

## Skills
Python, FastAPI, PostgreSQL, AWS, Docker, CI/CD, Terraform

## Motivation
Want to scale APIs & mentor juniors in a product-driven team.
```

*Если строки Candidate ID нет — в таблицу попадёт имя файла без расширения.*

---

## 🧠 Как работает pipeline

1. **Загрузка конфигов** (`config.yaml`, `.env`).
2. **Чтение системного промта** (`system_prompt.md`), где жёстко задан чеклист оценки.
3. **Для каждого кандидата**:

   * Собирает системный промт и резюме в одно сообщение (`system` role).
   * Отправляет в OpenAI Chat API с параметрами семплинга.
   * Парсит ответ: буква-оценка, объяснение, а также сохраняет полный raw JSON ответ модели.

4. **Сохраняет результаты**:

   * `results.md` — таблица для просмотра глазами (Candidate | Grade | Explanation).
   * `results.json` — подробный JSON, где raw\_response содержит весь чеклист, все критерии, оценки и комментарии LLM.

---

## 📊 Пример результата

### **results.md**

| Candidate | Grade | Explanation                                                                                                     |
| --------- | ----- | --------------------------------------------------------------------------------------------------------------- |
| C001      | A     | Отлично подходит как специалист и наставник, небольшие потенциальные проблемы с интеграцией в культуру компании |
| C016      | D     | Кандидат имеет опыт в HR, но отсутствует технический опыт и навыки, что не соответствует требованиям Aviasales  |

### **results.json**

```json
[
  {
    "candidate": "C001",
    "grade": "A",
    "score": 4,
    "explanation": "Отлично подходит как специалист и наставник, ...",
    "raw_response": "{...полный JSON чеклист LLM...}"
  },
  ...
]
```

В поле `"raw_response"` лежит полный JSON-ответ с чеклистами, баллами, плюсами/минусами — всё, как формирует LLM.

---

## 🏆 Под капотом: оценка по чеклисту (system prompt)

LLM получает промт с явным чеклистом:

* **Общие критерии (company-fit)**: опыт, мотивация, структурность, риски/плюсы для культуры
* **Локальные критерии (vacancy-fit)**: опыт по конкретной вакансии
* **Скоринг**:

  * по каждому критерию: “да”, “отчасти”, “нет” + микро-комментарий
  * common\_score, local\_score (0–50), total\_score (0–100)
  * Грейд: A (90–100), B (75–89), C (50–74), D (<50)
  * Описание плюсов и минусов для hiring manager
* **Формат**: валидный JSON (см. поле `raw_response`)

**Пример system\_prompt.md смотри в репозитории.**

---

## 🛡 Безопасность

* **.env** (API-ключ) **и все артефакты (results.\*) защищены через `.gitignore`** 
* **Pipeline хранит ключ в открытом виде**.

---

## ⚡️ Production-ready практики

* Явные docstrings, PEP484 type hints, обработка ошибок с retry/backoff
* Логика работы с OpenAI ≥1.12 SDK (client.chat.completions.create)
* Параметры семплинга и лимиты в YAML, а не в коде
* Стабильная структура файлов, легко расширяемый pipeline
* Автоматический парсинг чеклиста для честного, воспроизводимого grade

---

## ❓ FAQ

* **В: Как добавить ещё кандидатов?**

  * Просто положи новые `.md`-файлы в папку `candidates/` и перезапусти pipeline.

* **В: Как поменять модель/параметры?**

  * Отредактируй `config.yaml`, не забудь перезапустить скрипт.

* **В: Где смотреть подробную судейскую расшифровку?**

  * Открой `results.json`, смотри поле `"raw_response"`.

---

## 📝 Автор / поддержка

Разработка: [mityanos](https://github.com/mityanos)
Пожелания, багрепорты — через GitHub Issues.

---




# 002 - llm_resume_grader/config.yaml
# 002 - llm_resume_grader/config.yaml
llm:
  model: "gpt-4.1-mini-2025-04-14"

  params:
    temperature: 0.2
    top_p: 1.0
    frequency_penalty: 0
    presence_penalty: 0
    max_tokens: 1000

  retry_max: 6

grading:
  scale: {A: 4, B: 3, C: 2, D: 1}


paths:
  candidates_glob: "data/input/candidates/*.md"
  system_prompt:    "data/input/system_prompt.md"
  out_json:         "data/output/results.json"
  out_md_summary:   "data/output/results_summary.md"
  out_md_full:      "data/output/results_full.md"
  candidate_md_dir: "data/output/candidates_md"

# 003 - llm_resume_grader/data/input/candidates/Анна Смирнова.md
# Анна Смирнова  
Backend Lead / Middle Backend Engineer  
Москва, Россия | +7 912 123-45-67 | anna.smirnova@example.com  
LinkedIn: linkedin.com/in/anna-smirnova | GitHub: github.com/anna-smirnova  

---

## ЦЕЛЬ  
Стать частью команды Aviasales на позиции Middle Backend Engineer, применяя опыт в разработке высоконагруженных микросервисных систем на Python, FastAPI и PostgreSQL, а также развивая технологии CI/CD и облачную инфраструктуру на AWS/Terraform.

---

## КЛЮЧЕВЫЕ НАВЫКИ  
- **Языки:** Python (8 лет), SQL (5 лет), Bash  
- **Фреймворки:** FastAPI, Flask, Django REST Framework  
- **Базы данных:** PostgreSQL, Redis, Elasticsearch  
- **Облако:** AWS (EC2, S3, RDS, Lambda), Terraform (IaC)  
- **Контейнеризация:** Docker, Kubernetes (EKS)  
- **CI/CD:** GitLab CI, Jenkins, Ansible, Helm  
- **Системный дизайн:** микросервисы, event-driven (Kafka)  
- **Тестирование:** pytest, pytest-cov, integration tests, Tox  
- **Мониторинг:** Prometheus, Grafana, ELK Stack  
- **Разработка:** Clean Code, SOLID, Code Review, Agile/Scrum  

---

## ОПЫТ РАБОТЫ  

### Backend Lead, TechEdge Solutions (Москва)  
*Июнь 2020 – настоящее время*  
- Руководство командой из 5 backend-разработчиков: планирование, Code Review, менторство.  
- Проектирование микросервисной архитектуры на Python/FastAPI, PostgreSQL, Redis.  
- Terraform-модули для AWS (EC2 Auto Scaling, RDS Multi-AZ, S3), автоматизация, масштабирование до 500 инстансов.  
- CI/CD: GitLab CI, Docker, Kubernetes (EKS), Helm Charts, автоматические rollout/rollback.  
- Мониторинг: Prometheus, Grafana, ELK для логирования и алертинга.  
- Интеграция с Kafka, настройка consumer-групп, оптимизация throughput.  
- Оптимизация SQL-запросов, настройка репликации и резервного копирования.  
- Результат: время отклика API ↓45%, отказоустойчивость 99.99%.  

### Senior Python Developer, InnoTravel Co. (Москва)  
*Март 2017 – Май 2020*  
- RESTful API на Flask и Django REST Framework для системы рейсов.  
- ETL-пайплайн на Airflow, агрегирование данных маршрутов.  
- Интеграция с Amadeus, Sabre (GDS).  
- Docker, AWS EC2, Elastic Beanstalk — автоматизация деплоя.  
- Unit- и integration-тесты (pytest) с покрытием 85%.  
- Оптимизация latency ↓30% через Redis-кэширование и ORM-рефакторинг.  

### Python Developer, SoftSolutions (Москва)  
*Август 2014 – Февраль 2017*  
- Backend на Python 2.7, Django, поддержка PostgreSQL 9.3.  
- Linux-администрирование (Ubuntu), мониторинг (Nagios), деплой.  
- Code Review, рефакторинг legacy-кода, устранение багов.  

---

## ОБРАЗОВАНИЕ  
**Московский Государственный Технический Университет ГА (МИРЭА)**  
Бакалавр, Информатика и вычислительная техника  
Сентябрь 2010 – Июнь 2014  

- Тема диплома: «Разработка системы управления бронированием авиабилетов»  

---

## ДОПОЛНИТЕЛЬНОЕ ОБУЧЕНИЕ  
- AWS Certified Solutions Architect – Associate (2022)  
- Certified Kubernetes Application Developer (CKAD) (2021)  
- HashiCorp Certified: Terraform Associate (2020)  
- Курс «Designing Data-Intensive Applications» (Coursera, 2021)  
- Участие в митапах Python Moscow, DevOpsDays Moscow  

---

## ЯЗЫКИ  
- Русский — родной  
- Английский — Upper-Intermediate (B2)  
---
**Анна Смирнова**  
Телефон: +7 912 123-45-67  
E-mail: anna.smirnova@example.com  
LinkedIn: linkedin.com/in/anna-smirnova  

15 мая 2025  

Hiring Manager  
Aviasales  
Москва, Россия  

Уважаемая команда Aviasales,

Меня зовут Анна Смирнова, и я обращаюсь к вам с искренним интересом к вакансии Middle Backend Engineer. За последние 8 лет я развивалась как Backend Lead, работая над проектами высокой нагрузки, масштабируемыми API и микросервисами. Особое внимание уделяю качеству кода, инфраструктуре в облаке и автоматизации CI/CD-процессов. Я глубоко разделяю ценности Aviasales: стремление к инновациям, высоким стандартам надежности и открытости командного взаимодействия.

**Почему я могу принести пользу Aviasales:**  
1. **Опыт работы с high-load**: в качестве Backend Lead я отвечала за систему бронирования билетов с пиковыми нагрузками до 50 000 запросов в минуту.  
2. **Экспертиза в AWS & Terraform**: разработала и сопровождала инфраструктуру в AWS с использованием Terraform, обеспечив безотказную работу сервисов при масштабировании до 500+ инстансов.  
3. **Менторство и командная культура**: на текущем месте я обучаю и наставляю команду из пяти разработчиков, провожу code review и внедряю стандарты качества по Clean Code и SOLID.  

Хочу присоединиться к Aviasales, чтобы развивать и масштабировать backend-архитектуру, делиться опытом и учиться у экспертов ведущей компании в области travel-технологий.  

Готова к интервью в удобное для вас время.  

С уважением,  
Анна Смирнова  
---
### КЛЮЧЕВЫЕ ДОСТИЖЕНИЯ
- **0-downtime миграция**: спроектировала и руководила переносом монолита на микросервисы с минимальным простоем, рост TPS +40%.  
- **Оптимизация производительности**: индексы и query profiling → время отклика ↓60% в критических узлах.  
- **Автоматизация инфраструктуры**: Terraform-модули для AWS → ручные операции ↓80%.  
- **Разработка API**: FastAPI-сервис для платежей, выдерживает 10 000 RPS с отказоустойчивостью.  
- **Менторство**: провела образовательные сессии по тестированию и архитектуре → качество кода ↑25%.

---

### ПРОЕКТЫ
1. **Сервис бронирования билетов high-load**  
   - FastAPI, PostgreSQL, Redis, Kubernetes, Helm.  
   - Обработка до 50 000 запросов/мин, бесперебойная работа в пик.  
2. **Сервис учета платежей**  
   - FastAPI, Celery, RabbitMQ, Docker.  
   - Обработка через Stripe, интеграция с внешними провайдерами.  
3. **Переезд базы данных**  
   - Миграция Monolith PostgreSQL → кластерный Multi-AZ, минимизация downtime.  

---

### ПРОФЕССИОНАЛЬНЫЕ ИНСТРУМЕНТЫ
- **Тестирование:** pytest, pytest-cov, integration tests  
- **Мониторинг:** Prometheus, Grafana, ELK Stack  
- **CI/CD:** GitLab CI, Jenkins, Ansible, Helm  
- **Облачные:** AWS (EC2, RDS, S3, Lambda), Terraform  
- **Контейнеризация:** Docker, Kubernetes (EKS)  
- **Инструменты:** Jira, Confluence, Slack, VSCode, PyCharm

---

### ЛИЧНЫЕ КАЧЕСТВА
- Ответственность, внимание к деталям  
- Проактивность, самостоятельное решение задач  
- Командная работа, открытость к новым знаниям  
- Стрессоустойчивость, адаптивность к изменениям  


# 004 - llm_resume_grader/data/input/candidates/Виктория Петрова.md
# Виктория Петрова  
Data Analyst → Junior Backend Developer  
Москва, Россия | +7 901 789-12-34 | viktoria.petrovа@example.com  
LinkedIn: linkedin.com/in/viktoriapetrova | GitHub: github.com/viktoriapetrova  

---

## ЦЕЛЬ  
Перейти на позицию Junior/Middle Backend Developer в Aviasales, применить навыки Python и SQL, а также развивать компетенции во фреймворках Flask/FastAPI и облачных технологиях.

---

## КЛЮЧЕВЫЕ НАВЫКИ  
- **Языки:** Python (4 года), SQL (4 года), Bash (средний)  
- **Фреймворки:** Flask (1 год), FastAPI (6 месяцев)  
- **Базы данных:** PostgreSQL (2 года базовый уровень), MySQL (1 год), SQLite  
- **Облако:** AWS (EC2, S3) — базовый уровень  
- **Контейнеризация:** Docker — начальный уровень  
- **Аналитика:** Pandas, NumPy, Matplotlib, Seaborn  
- **BI:** Tableau, Power BI  
- **Тестирование:** pytest (базовый)  
- **Методологии:** Scrum, Kanban, Jira  
- **Инструменты:** Git, GitHub, VSCode, Jupyter Notebook  

---

## ОПЫТ РАБОТЫ  

### Data Analyst, BizData Consult (Москва)  
*Июнь 2021 – настоящее время*  
- Сбор, очистка, анализ данных клиентов (Excel, CSV, PostgreSQL).  
- ETL-процессы на Python (Pandas, SQLAlchemy): загрузка и трансформация данных.  
- Визуализация в Tableau и Power BI: дашборды для руководства.  
- Оптимизация SQL-запросов в PostgreSQL: время выполнения ↓50%.  
- Поддержка резервного копирования/восстановления базы данных.  

### Python Developer (Intern), ITStart Lab (Москва)  
*Сентябрь 2020 – Май 2021*  
- Разработка внутреннего веб-приложения на Flask: CRUD и REST API.  
- Docker-контейнеры для локальной разработки и тестирования.  
- Unit-тесты на pytest: покрытие 60%.  
- Документация API в Swagger/OpenAPI.  

---

## ОБРАЗОВАНИЕ  
**Московский Финансово-Технический Университет (МФТУ)**  
Бакалавр, Прикладная информатика  
Сентябрь 2017 – Июнь 2021  

- Диплом: «Автоматизация отчётов на основе PostgreSQL и Python»  

---

## ДОПОЛНИТЕЛЬНОЕ ОБУЧЕНИЕ  
- «Introduction to Flask» (Udemy, 2021)  
- «Python for Data Science» (Coursera, 2020)  
- «KursDev Backend Bootcamp» (онлайн, 2022)  

---

## ЯЗЫКИ  
- Русский — родной  
- Английский — Intermediate (B1)  
---
**Виктория Петрова**  
Телефон: +7 901 789-12-34  
E-mail: viktoria.petrovа@example.com  
LinkedIn: linkedin.com/in/viktoriapetrova  

25 мая 2025  

HR Department  
Aviasales  
Москва, Россия  

Здравствуйте, уважаемые рекрутеры Aviasales!

Меня зовут Виктория Петрова. В последние четыре года я работала Data Analyst в небольшой консалтинговой компании, где занималась сбором и обработкой данных, визуализацией показателей и автоматизацией отчетности. С недавнего времени я увлеклась backend-разработкой и прошла несколько онлайн-курсов по Python («Python for Data Science», «Introduction to Flask»), а также самостоятельно написала несколько небольших API-сервисов для собственных проектов.

Я хочу продолжить развитие в области backend-разработки и верю, что Aviasales как лидер в travel-технологиях даст мне отличную возможность учиться у сильной команды. Я готова быстро погружаться в задачи, учиться у опытных коллег и применять полученные знания на практике.

**Что могу предложить Aviasales:**  
- **Python & SQL:** 4 года опыта работы с Pandas, Jupyter, построением запросов к PostgreSQL (базовый уровень).  
- **Flask & FastAPI (начальный уровень):** разработала prototype API для внутреннего использования (1 000–2 000 запросов в день).  
- **Аналитика и визуализация:** опыт построения дашбордов для руководства на Tableau и Power BI.  

Над чем буду работать:  
- Активно изучаю Kubernetes и Docker, планирую пройти курс «Docker и Kubernetes для разработчиков».  
- Начинаю учить AWS (бесплатные лаборатории EC2 и S3).  

Буду признательна за возможность пройти интервью и показать свои способности.

С уважением,  
Виктория Петрова  
---
### КЛЮЧЕВЫЕ ДОСТИЖЕНИЯ
- **Автоматизация отчётов:** ETL-пайплайн на Python (Pandas, SQLAlchemy) → ручной труд ↓60%.  
- **Собственный Flask API:** CRUD-сервис для задач (PostgreSQL), Docker-контейнеризация, развернут на удалённом сервере.  
- **Data Visualization Dashboard:** дашборд в Tableau для финансовых показателей, одобрено руководством.  
- **SQL-оптимизация:** долгие запросы переписал, время выполнения ↓50%.  

---

### ПРОФЕССИОНАЛЬНЫЕ ИНСТРУМЕНТЫ
- **Python, SQL, Bash**  
- **Flask, FastAPI (начальный)**  
- **PostgreSQL, MySQL, SQLite**  
- **AWS (EC2, S3) — базовый уровень**  
- **Docker — базовый**  
- **Tableau, Power BI**  
- **pytest (базовый)**  
- **Git, GitHub, VSCode, Jupyter Notebook**  
- **Jira, Scrum, Kanban**  

---

### ЛИЧНЫЕ КАЧЕСТВА
- Быстро обучаюсь, заинтересованность в backend-разработке  
- Ответственность, системное мышление  
- Командная работа, готовность принимать и давать фидбэк  
- Упорство и настойчивость в решении сложных задач  


# 005 - llm_resume_grader/data/input/candidates/Михаил Иванов.md
# Михаил Иванов  
Backend Developer  
Москва, Россия | +7 916 654-32-10 | m.ivanov.talents@example.com  
LinkedIn: linkedin.com/in/mikhail-ivanov | GitHub: github.com/mikhail-ivanov  

---

## ЦЕЛЬ  
Занять позицию Middle Backend Engineer в Aviasales, применить свои навыки разработки на Python/FastAPI, PostgreSQL и Docker, а также развивать компетенции в AWS и DevOps.

---

## КЛЮЧЕВЫЕ НАВЫКИ  
- **Языки:** Python (5 лет), SQL (4 года), Bash  
- **Фреймворки:** FastAPI (2 года), Flask (2 года), Django (1 год)  
- **Базы данных:** PostgreSQL (3 года), MySQL (1 год), Redis (1 год)  
- **Облако:** AWS (EC2, RDS), начальные знания Terraform  
- **Контейнеризация:** Docker (2 года), базовые знания Kubernetes  
- **CI/CD:** GitLab CI, GitHub Actions  
- **Тестирование:** pytest, unittest  
- **Мониторинг:** Grafana (базовая настройка), CloudWatch  
- **Методологии:** Agile/Scrum, Jira, Confluence  

---

## ОПЫТ РАБОТЫ  

### Backend Developer, FinanceWare (Москва)  
*Июль 2021 – настоящее время*  
- Разработка микросервисов на Python/FastAPI, PostgreSQL, Redis.  
- Оптимизация REST API (profiling, рефакторинг запросов, кеширование).  
- Dockerfile и docker-compose для окружения разработчика.  
- CI/CD с GitLab CI: автоматизированное тестирование, сборка и развертывание.  
- Интеграция с AWS RDS PostgreSQL: шардирование, восстановление из снимков.  
- Pytest: написала более 200 тестов, покрытие 75%.  
- Мониторинг метрик через Grafana + оповещения Slack.  

**Проекты:**  
1. **API платежей**  
   - FastAPI, PostgreSQL, Redis, Docker, GitLab CI.  
   - Нагрузка до 5 000 RPS, latency <100 мс.  
2. **Сервис отчетов**  
   - Flask, Celery, RabbitMQ, PostgreSQL.  
   - Автоматическая генерация PDF-отчетов.  

### Python Developer, TechInno (Москва)  
*Апрель 2019 – Июнь 2021*  
- Разработка CRM на Flask/Django, интеграция 1C через SOAP.  
- Поддержка MySQL: сложные SQL-запросы, индексы.  
- CI: GitHub Actions, деплой на Heroku.  
- Code Review, участие в Scrum.  

**Проекты:**  
1. **CRM для медтех-компании**  
   - Django REST, PostgreSQL, SOAP-интеграция.  
2. **Агрегатор данных**  
   - Flask, BeautifulSoup для scraping.  

### Junior Python Developer, SoftDev Lab (Москва)  
*Сентябрь 2017 – Март 2019*  
- Web-сервисы на Flask, администрирование Ubuntu (Nginx, Gunicorn).  
- MySQL: резервное копирование, оптимизация запросов.  
- Скрипты на Bash для логирования, обработки файлов.  

---

## ОБРАЗОВАНИЕ  
**Московский Институт Технологий (МИТ)**  
Бакалавр, Прикладная математика и информатика  
Сентябрь 2013 – Июнь 2017  

- Диплом: «Разработка прототипа RESTful API для финансового сервиса»  

---

## ДОПОЛНИТЕЛЬНОЕ ОБУЧЕНИЕ  
- «FastAPI. Профессиональная разработка» (Udemy, 2022)  
- «Основы AWS для разработчиков» (Coursera, 2021)  
- Участие в PyCon Russia (2022, 2023)  

---

## ЯЗЫКИ  
- Русский — родной  
- Английский — Intermediate (B1)  

# 005 - llm_resume_grader/data/input/candidates/Михаил Иванов.md
# Михаил Иванов  
Backend Developer  
Москва, Россия | +7 916 654-32-10 | m.ivanov.talents@example.com  
LinkedIn: linkedin.com/in/mikhail-ivanov | GitHub: github.com/mikhail-ivanov  

---

## ЦЕЛЬ  
Занять позицию Middle Backend Engineer в Aviasales, применить свои навыки разработки на Python/FastAPI, PostgreSQL и Docker, а также развивать компетенции в AWS и DevOps.

---

## КЛЮЧЕВЫЕ НАВЫКИ  
- **Языки:** Python (5 лет), SQL (4 года), Bash  
- **Фреймворки:** FastAPI (2 года), Flask (2 года), Django (1 год)  
- **Базы данных:** PostgreSQL (3 года), MySQL (1 год), Redis (1 год)  
- **Облако:** AWS (EC2, RDS), начальные знания Terraform  
- **Контейнеризация:** Docker (2 года), базовые знания Kubernetes  
- **CI/CD:** GitLab CI, GitHub Actions  
- **Тестирование:** pytest, unittest  
- **Мониторинг:** Grafana (базовая настройка), CloudWatch  
- **Методологии:** Agile/Scrum, Jira, Confluence  

---

## ОПЫТ РАБОТЫ  

### Backend Developer, FinanceWare (Москва)  
*Июль 2021 – настоящее время*  
- Разработка микросервисов на Python/FastAPI, PostgreSQL, Redis.  
- Оптимизация REST API (profiling, рефакторинг запросов, кеширование).  
- Dockerfile и docker-compose для окружения разработчика.  
- CI/CD с GitLab CI: автоматизированное тестирование, сборка и развертывание.  
- Интеграция с AWS RDS PostgreSQL: шардирование, восстановление из снимков.  
- Pytest: написала более 200 тестов, покрытие 75%.  
- Мониторинг метрик через Grafana + оповещения Slack.  

**Проекты:**  
1. **API платежей**  
   - FastAPI, PostgreSQL, Redis, Docker, GitLab CI.  
   - Нагрузка до 5 000 RPS, latency <100 мс.  
2. **Сервис отчетов**  
   - Flask, Celery, RabbitMQ, PostgreSQL.  
   - Автоматическая генерация PDF-отчетов.  

### Python Developer, TechInno (Москва)  
*Апрель 2019 – Июнь 2021*  
- Разработка CRM на Flask/Django, интеграция 1C через SOAP.  
- Поддержка MySQL: сложные SQL-запросы, индексы.  
- CI: GitHub Actions, деплой на Heroku.  
- Code Review, участие в Scrum.  

**Проекты:**  
1. **CRM для медтех-компании**  
   - Django REST, PostgreSQL, SOAP-интеграция.  
2. **Агрегатор данных**  
   - Flask, BeautifulSoup для scraping.  

### Junior Python Developer, SoftDev Lab (Москва)  
*Сентябрь 2017 – Март 2019*  
- Web-сервисы на Flask, администрирование Ubuntu (Nginx, Gunicorn).  
- MySQL: резервное копирование, оптимизация запросов.  
- Скрипты на Bash для логирования, обработки файлов.  

---

## ОБРАЗОВАНИЕ  
**Московский Институт Технологий (МИТ)**  
Бакалавр, Прикладная математика и информатика  
Сентябрь 2013 – Июнь 2017  

- Диплом: «Разработка прототипа RESTful API для финансового сервиса»  

---

## ДОПОЛНИТЕЛЬНОЕ ОБУЧЕНИЕ  
- «FastAPI. Профессиональная разработка» (Udemy, 2022)  
- «Основы AWS для разработчиков» (Coursera, 2021)  
- Участие в PyCon Russia (2022, 2023)  

---

## ЯЗЫКИ  
- Русский — родной  
- Английский — Intermediate (B1)  
---
**Михаил Иванов**  
Телефон: +7 916 654-32-10  
E-mail: m.ivanov.talents@example.com  
LinkedIn: linkedin.com/in/mikhail-ivanov  

20 мая 2025  

HR Team  
Aviasales  
Москва, Россия  

Здравствуйте, уважаемая команда Aviasales!

Меня зовут Михаил Иванов, у меня пятилетний опыт backend-разработчика, преимущественно в области финансовых сервисов. С тех пор как я впервые столкнулся с FastAPI и PostgreSQL, я понял, что хочу строить масштабируемые API и оптимизировать их производительность. За последний год я активно разрабатывал проект на FastAPI, Docker и GitLab CI, а также участвовал в запуске нескольких других микросервисов в облаке AWS.  

**Почему Aviasales?**  
- Ваша компания лидирует в индустрии travel-технологий. Мне близки ваши ценности: клиентоориентированный подход и использование современной инфраструктуры.  
- Я стремлюсь развиваться в роли Middle Backend Engineer, и уверен, что смогу быстро погрузиться в ваши практики разработки и DevOps.  

Мои сильные стороны:  
- **FastAPI & PostgreSQL**: 2 года проектирования и поддержки production-приложений, опыт написания сложных SQL-запросов (оптимизация запросов, индексы).  
- **Docker & CI/CD**: автоматизация процессов сборки контейнеров, разворачивание окружений через GitLab CI/CD.  
- **AWS (базовый уровень)**: создание EC2-инстансов, настройка RDS PostgreSQL.  

Есть, над чем работать:  
- Недостаточно опыта с Terraform и Kubernetes, но в настоящее время прохожу онлайн-курсы по Kubernetes (CKA Foundation).  
- Планирую углубить знания в области масштабируемых очередей (Kafka) и интегрировать их в текущие проекты.  

Буду рад подробнее рассказать о своём опыте на интервью.  

С уважением,  
Михаил Иванов  
---
### КЛЮЧЕВЫЕ ДОСТИЖЕНИЯ
- **FastAPI-проект с нагрузкой до 5 000 RPS**: повысил производительность, снизив время отклика с 200 мс до 90 мс.  
- **Оптимизация SQL**: рефакторинг запросов → время выполнения ↓40%.  
- **Автоматизация сборки**: Docker + GitLab CI → развертывание dev/test/prod окружений полностью автоматизировано.  
- **Обучение команды**: воркшопы по FastAPI и pytest → покрытие тестами ↑20%.  

---

### ПРОФЕССИОНАЛЬНЫЕ ИНСТРУМЕНТЫ
- **Docker, Kubernetes (начальный)**  
- **GitLab CI, GitHub Actions**  
- **pytest, unittest**  
- **Grafana, CloudWatch**  
- **AWS (EC2, RDS)**  
- **Jira, Confluence, Slack**  

---

### ЛИЧНЫЕ КАЧЕСТВА
- Самостоятельность, быстрая обучаемость  
- Коммуникативность, умение работать в команде  
- Ответственность, желание развиваться  
- Упорство в решении сложных задач  


# 006 - llm_resume_grader/data/input/system_prompt.md
# Системный промпт: AI-ассистент по найму

## Роль: AI-ассистент по найму Aviasales

Ты — AI-ассистент, задача которого — честно и прозрачно оценивать отклики кандидатов по двум уровням (компания и вакансия), используя явный чеклист из 4 критериев для каждого уровня. Перед каждым итоговым выводом кратко опиши свои рассуждения CoT по пунктам чеклиста (но не по подсчёту scores).

---

### Общая инструкция (Company-fit)

Требования ко всем сотрудникам Aviasales:
- Опыт backend-разработки high-load сервисов на Python (>=3 лет)
- Знание AWS (EC2, S3) и Terraform (>=2 года)
- Умение работать в Agile-команде и проводить code review
- Английский язык на уровне не ниже B1

### Локальная инструкция (Vacancy-fit)

Критерии по вакансии «Middle Backend Engineer»:
- Опыт работы с FastAPI и PostgreSQL (>=2 года)
- Опыт контейнеризации (Docker, Kubernetes)
- Написание юнит-тестов (pytest, coverage)
- Знание CI/CD (GitLab CI или Jenkins)

---

## Входные данные

Отклики кандидатов по одному, содержат:
- Резюме
- Сопроводительное письмо
- Доп. портфолио/материалы (если есть)

---

## Что ты должен делать для каждого отклика:

1. **Company-fit (CoT + чеклист):**
   - Сначала напиши 1–2 предложения Chain-of-Thought по общим требованиям (например, «Кандидат имеет 8 лет опыта на Python, но не упомянул Terraform…»).
   - Затем пройди чеклист:
     1. Совпадает ли ключевой опыт и стек?  
        *Результат: «да/отчасти/нет» + 1–2 предложения аргументации.*
     2. Ясно ли выражена мотивация работать в Aviasales?  
        *Результат: «да/отчасти/нет» + 1–2 предложения аргументации.*
     3. Насколько чётко и ясно структурированы материалы?  
        *Результат: «да/отчасти/нет» + 1–2 предложения аргументации.*
     4. Есть ли риски или выдающиеся плюсы для культуры компании?  
        *Результат: «да/отчасти/нет» + 1–2 предложения аргументации.*
   - Посчитай `common_score` (число 0–50 без лишних символов).  
     *Напиши короткий комментарий (1–2 предложения) для пояснения оценки (например, «common_score: 35»).*

2. **Vacancy-fit (CoT + чеклист):**
   - Напиши 1–2 предложения Chain-of-Thought по локальным требованиям (например, «У кандидата есть опыт с FastAPI, но мало опыта с Kubernetes…»).
   - Затем пройди чеклист:
     1. Совпадает ли опыт/стек с локальными требованиями?  
        *Результат: «да/отчасти/нет» + 1–2 предложения аргументации.*
     2. Чётко ли описана мотивация под эту роль?  
        *Результат: «да/отчасти/нет» + 1–2 предложения аргументации.*
     3. Насколько аккуратно подано резюме/письмо под требования вакансии?  
        *Результат: «да/отчасти/нет» + 1–2 предложения аргументации.*
     4. Есть ли риски или сильные стороны, релевантные вакансии?  
        *Результат: «да/отчасти/нет» + 1–2 предложения аргументации.*
   - Посчитай `local_score` (число 0–50 без лишних символов).  
     *Напиши короткий комментарий (1–2 предложения) для пояснения оценки (например, «local_score: 40»).*

3. **Суммарная оценка:**
   - `total_score = common_score + local_score` (число 0–100 без лишних символов).
   - Напиши короткое пояснение (1–2 предложения) для `total_score` (например, «total_score: 75»).

4. **Грейдинг:**
   - A (90–100): точное попадание в оба уровня.  
   - B (75–89): в целом подходит, есть 1–2 несущественных минуса.  
   - C (50–74): частичное совпадение, явные пробелы.  
   - D (<50): нет релевантности или нечитаемый формат.  
   - Формат строки:
     ```
     Grade: <A|B|C|D> – <1–2 предложения объяснения>
     ```

5. **Комментарий рекрутёра (pros/cons):**
   - Напиши 1–2 предложения Chain-of-Thought, почему именно эти pros и cons.  
   - `pros` (2–3 пункта, по существу, с учётом чеклистов).  
   - `cons` (1–3 пункта, чётко и конструктивно).

6. **Если резюме нечитаемо или отсутствует раздел «Motivation»:**
   - Сразу выдавай:
     ```json
     {
       "common_checklist": [],
       "common_score": 0,
       "common_score_comment": "",
       "local_checklist": [],
       "local_score": 0,
       "local_score_comment": "",
       "total_score": 0,
       "total_score_comment": "",
       "grade": "D",
       "grade_explanation": "Невозможно оценить: формат или контент неполный",
       "comment": {"pros": [], "cons": ["Нечитаемое или неполное резюме"]}
     }
     ```
   - Без чеклистов и CoT.

---

## Формат финального ответа

```json
{
  "common_checklist": [
    {
      "criterion": "<Название>",
      "result": "<да/отчасти/нет>",
      "comment": "<1–2 предложения аргументации>"
    }
  ],
  "common_score": 35,
  "common_score_comment": "Кандидат имеет релевантный опыт, но не упомянул Terraform.",
  "local_checklist": [
    {
      "criterion": "<Название>",
      "result": "<да/отчасти/нет>",
      "comment": "<1–2 предложения аргументации>"
    }
  ],
  "local_score": 40,
  "local_score_comment": "Есть опыт с FastAPI, но недостаточно опыта с PostgreSQL.",
  "total_score": 75,
  "total_score_comment": "Суммарный балл показывает соответствие большинству требований.",
  "grade": "B",
  "grade_explanation": "Кандидат соответствует большинству требований, но есть пробел в PostgreSQL.",
  "comment": {
    "pros": ["Опыт с FastAPI и AWS Lambda", "Чёткая мотивация под роль"],
    "cons": ["Мало опыта с PostgreSQL (<2 года)"]
  }
}
````

---

## Примеры:

### Grade A

```markdown
# Chain-of-Thought (Company-fit)
Кандидат имеет 8 лет опыта на Python и упомянул Terraform—это точно совпадает с требованиями.

* Relevance of skills and experience: да  
  "8 лет опыта на Python и Terraform совпадает с требованиями Aviasales."  
* Motivation for the role: да  
  "Чётко выражил желание масштабировать API и наставлять."
* Communication and clarity: да  
  "Резюме структурировано и без лишних деталей."  
* Red flags or outstanding strengths: нет  
  "Нет рисков, сильная сторона—миграции без простоев."

common_score: 50  
common_score_comment: "Идеальное совпадение по всем четырём пунктам."

# Chain-of-Thought (Vacancy-fit)
Кандидат работал с FastAPI и PostgreSQL более 2 лет, есть Docker и опыт DevOps.

* Relevance of skills and experience: да  
  "FastAPI и PostgreSQL в опыте—абсолютно соответствует."  
* Motivation for the role: да  
  "Хочет масштабировать API в условиях вакансии."  
* Communication and clarity: да  
  "Резюме адаптировано под вакансию: перечислены нужные технологии."  
* Red flags or outstanding strengths: нет  
  "Нет рисков, все навыки покрывают требования."

local_score: 50  
local_score_comment: "Полное совпадение по локальным требованиям."

total_score: 100  
total_score_comment: "Максимальный итоговый балл."

Grade: A – Кандидат полностью соответствует требованиям по всем критериям.  
pros: ["8 лет опыта на Python и Terraform", "Чёткая мотивация под роль"]  
cons: []
```

---

### Grade B

```markdown
# Chain-of-Thought (Company-fit)
Есть 4 года опыта в HealthTech, но нет упоминания Terraform.

* Relevance of skills and experience: отчасти  
  "Опыт 4 года на Python, но без Terraform."  
* Motivation for the role: да  
  "Желание работать в масштабном продукте понятное."  
* Communication and clarity: да  
  "Резюме читаемо."  
* Red flags or outstanding strengths: отчасти  
  "Отсутствие Terraform—незначительный риск."

common_score: 35  
common_score_comment: "Большинство совпадает, но есть пробел в Terraform."

# Chain-of-Thought (Vacancy-fit)
Есть опыт с FastAPI, но PostgreSQL менее 2 лет.

* Relevance of skills and experience: отчасти  
  "FastAPI есть, но небольшой опыт с PostgreSQL."  
* Motivation for the role: да  
  "Стремится работать с DevOps-технологиями."  
* Communication and clarity: да  
  "Резюме сфокусировано на нужных темах."  
* Red flags or outstanding strengths: отчасти  
  "Мало опыта с PostgreSQL, но есть AWS Lambda."

local_score: 40  
local_score_comment: "Почти всё совпадает, но пробел с PostgreSQL."

total_score: 75  
total_score_comment: "Суммарный балл на границе между B и C."

Grade: B – Кандидат соответствует большинству требований, есть пробел в PostgreSQL.  
pros: ["Опыт с FastAPI и AWS Lambda", "Чёткая мотивация"]  
cons: ["Недостаточно опыта с PostgreSQL"]
```

---

### Grade C

```markdown
# Chain-of-Thought (Company-fit)
Кандидат 3 года работал аналитиком, есть базовый Python, но нет AWS/Terraform.

* Relevance of skills and experience: отчасти  
  "Python есть, но нет опыта с AWS и Terraform."  
* Motivation for the role: отчасти  
  "Хотела бы перейти в backend, но опыта мало."  
* Communication and clarity: да  
  "Резюме структурировано."  
* Red flags or outstanding strengths: есть  
  "Нет релевантного опыта—большой риск."

common_score: 20  
common_score_comment: "Только частично пересекаются навыки, серьёзный пробел."

# Chain-of-Thought (Vacancy-fit)
Есть базовый Flask, но нет FastAPI и PostgreSQL, мотивация поверхностна.

* Relevance of skills and experience: отчасти  
  "Flask есть, FastAPI и PostgreSQL отсутствуют."  
* Motivation for the role: отчасти  
  "Хочет менторства, но неясно, почему именно эта вакансия."  
* Communication and clarity: да  
  "Резюме понятно, но общий уровень."  
* Red flags or outstanding strengths: есть  
  "Нет ключевого опыта backend."

local_score: 25  
local_score_comment: "Неполное совпадение по навыкам, мотивация поверхностная."

total_score: 45  
total_score_comment: "Суммарный балл указывает на частичное совпадение."

Grade: C – Есть Python и SQL, но нет опыта backend-разработки, мотивация поверхностна.  
pros: ["Основы Python и Flask", "Структурированное резюме"]  
cons: ["Нет опыта с FastAPI и PostgreSQL", "Мотивация не достаточно раскрыта"]
```

---

### Grade D

```markdown
# Chain-of-Thought (Company-fit)
Кандидат 6 лет занимался графическим дизайном, нет IT-опыта.

* Relevance of skills and experience: нет  
  "Нет опыта разработки."  
* Motivation for the role: нет  
  "Интерес есть, но нет реальных шагов к backend."  
* Communication and clarity: да  
  "Резюме структурировано, но не по теме."  
* Red flags or outstanding strengths: есть  
  "Профиль вне сферы IT."

common_score: 0  
common_score_comment: "Нет совпадения по основным требованиям."

# Chain-of-Thought (Vacancy-fit)
Нет навыков and мотивация нерелевантна.

* Relevance of skills and experience: нет  
  "Графический дизайн, не backend."  
* Motivation for the role: нет  
  "Не начинал учиться backend."  
* Communication and clarity: да  
  "Резюме читаемо, но не по вакансии."  
* Red flags or outstanding strengths: есть  
  "Профиль вне сферы IT."

local_score: 0  
local_score_comment: "Нет совпадения по локальным требованиям."

total_score: 0  
total_score_comment: "Полное несовпадение."

Grade: D – Резюме вне сферы IT, невозможно оценить пригодность.  
pros: []  
cons: ["Профиль не соответствует требованиям", "Нет релевантных навыков"]
```

---

### Кандидат-ошибка

```markdown
# Chain-of-Thought (Error)
Ответ модели не содержит JSON или строки «Grade: …».

!ATTENTION!
* Relevance of skills and experience: нет  
  "Модель не вернула JSON, некорректный формат."  
* Motivation for the role: нет  
  "Отсутствует понятный вывод."  
* Communication and clarity: нет  
  "Нет читаемого результата."  
* Red flags or outstanding strengths: нет  
  "Невозможно оценить."

common_score: 0  
common_score_comment: ""
local_score: 0  
local_score_comment: ""
total_score: 0  
total_score_comment: ""

Grade: D – Ответ модели не соответствует формату JSON или `Grade:`.  
pros: []  
cons: ["Не валидный вывод модели"]
```


# 007 - llm_resume_grader/data/output/candidates_md/Анна_Смирнова.md
**Grade:** A (total_score: 100)  

## Анна Смирнова

**Company-fit = 50**  
“Идеальное совпадение по всем четырём пунктам общего чеклиста.”

**Vacancy-fit = 50**  
“Полное совпадение по локальным требованиям вакансии.”

**Grade Explanation**  
“Кандидат полностью соответствует требованиям по всем критериям, имеет сильный опыт и мотивацию.”


**Pros**  
- 8 лет опыта на Python с акцентом на high-load backend  
- Глубокие знания AWS и Terraform с практическим опытом масштабирования  
- Чёткая и мотивированная цель работать в Aviasales, опыт менторства и лидерства  

**Cons**  
- (нет)  

# 008 - llm_resume_grader/data/output/candidates_md/Виктория_Петрова.md
**Grade:** C (total_score: 60)  

## Виктория Петрова

**Company-fit = 30**  
“Кандидат имеет релевантный опыт Python и AWS, но отсутствует опыт Terraform, что снижает соответствие.”

**Vacancy-fit = 30**  
“Кандидат частично соответствует локальным требованиям, но опыт с Docker и CI/CD ограничен.”

**Grade Explanation**  
“Кандидат имеет базовые навыки backend-разработки и мотивацию, но недостаточно опыта с ключевыми технологиями для Middle уровня.”


**Pros**  
- Опыт работы с Python и базовый опыт AWS  
- Чёткая мотивация развиваться в backend и работать в Aviasales  
- Структурированное и понятное резюме с планами на обучение  

**Cons**  
- Отсутствует опыт с Terraform  
- Недостаточный опыт с FastAPI и Docker для Middle уровня  
- Нет упоминания о CI/CD опыте  

# 009 - llm_resume_grader/data/output/candidates_md/Михаил_Иванов.md
**Grade:** A (total_score: 93)  

## Михаил Иванов

**Company-fit = 48**  
“Отличное соответствие общим требованиям, небольшой пробел в опыте Terraform компенсируется желанием учиться.”

**Vacancy-fit = 45**  
“Хорошее соответствие локальным требованиям, есть небольшой пробел по Kubernetes и Terraform.”

**Grade Explanation**  
“Кандидат полностью соответствует требованиям компании и вакансии, мотивация и опыт хорошо выражены.”


**Pros**  
- 5 лет опыта backend-разработки на Python с использованием FastAPI и PostgreSQL  
- Опыт работы с AWS (EC2, RDS) и CI/CD (GitLab CI)  
- Чётко выраженная мотивация и структурированное резюме  

**Cons**  
- Ограниченный опыт с Terraform и Kubernetes, но есть планы на обучение  

# 010 - llm_resume_grader/data/output/results_summary.md
| Candidate | Grade | Explanation |
|-----------|-------|-------------|
| [Анна Смирнова](candidates_md/Анна_Смирнова.md) | A | **Grade Explanation**<br>“Кандидат полностью соответствует требованиям по всем критериям, имеет сильный опыт и мотивацию.”<br>**Pros**<br>- 8 лет опыта на Python с акцентом на high-load backend<br>- Глубокие знания AWS и Terraform с практическим опытом масштабирования<br>- Чёткая и мотивированная цель работать в Aviasales, опыт менторства и лидерства<br>**Cons**<br>- (нет) |
| [Михаил Иванов](candidates_md/Михаил_Иванов.md) | A | **Grade Explanation**<br>“Кандидат полностью соответствует требованиям компании и вакансии, мотивация и опыт хорошо выражены.”<br>**Pros**<br>- 5 лет опыта backend-разработки на Python с использованием FastAPI и PostgreSQL<br>- Опыт работы с AWS (EC2, RDS) и CI/CD (GitLab CI)<br>- Чётко выраженная мотивация и структурированное резюме<br>**Cons**<br>- Ограниченный опыт с Terraform и Kubernetes, но есть планы на обучение |
| [Виктория Петрова](candidates_md/Виктория_Петрова.md) | C | **Grade Explanation**<br>“Кандидат имеет базовые навыки backend-разработки и мотивацию, но недостаточно опыта с ключевыми технологиями для Middle уровня.”<br>**Pros**<br>- Опыт работы с Python и базовый опыт AWS<br>- Чёткая мотивация развиваться в backend и работать в Aviasales<br>- Структурированное и понятное резюме с планами на обучение<br>**Cons**<br>- Отсутствует опыт с Terraform<br>- Недостаточный опыт с FastAPI и Docker для Middle уровня<br>- Нет упоминания о CI/CD опыте |

# 011 - llm_resume_grader/main.py
# llm_resume_grader/main.py
#!/usr/bin/env python3
"""
LLM-powered résumé grader (single-message edition).
Reads inputs from llm_resume_grader/data/input/, writes outputs to llm_resume_grader/data/output/
and generates per-candidate Markdown files in data/output/candidates_md/.
"""

from __future__ import annotations

import os
import json
import logging
import re
import time
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError

# --- утилита для перевода относительных путей в абсолютные ------------------
# Каталог llm_resume_grader/ — единственный «корень» для относительных путей
BASE_DIR = Path(__file__).resolve().parent          # .../llm_resume_grader

def abs_path(rel: str | Path) -> Path:
    """Сделать абсолютный путь относительно llm_resume_grader/."""
    return (BASE_DIR / rel).resolve()


# ───────────────────────── helpers ──────────────────────────

def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )


def load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_env() -> None:
    load_dotenv(dotenv_path=BASE_DIR / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY missing in .env")


def read_text(path: str | Path) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()


def load_system_prompt(path: str | Path) -> str:
    return read_text(path)


def candidate_id(text: str, fallback: str) -> str:
    """
    Extracts "Candidate ID: <ID>" from the text, or uses fallback (filename) if not found.
    """
    match = re.search(r"Candidate ID:\s*([^\s\n]+)", text)
    return match.group(1) if match else fallback


def build_message(sys_prompt: str, cand_doc: str) -> List[Dict[str, str]]:
    """
    Combines the system prompt and candidate Markdown into one chat message sequence.
    """
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"```markdown\n{cand_doc}\n```"}
    ]


def safe_chat(
    client: OpenAI,
    messages: list[dict[str, str]],
    model: str,
    retry_max: int,
    **params,  # temperature, top_p, max_tokens, …
) -> str:
    """
    Sends messages to OpenAI Chat API with retries on RateLimitError or APIError.
    """
    for attempt in range(1, retry_max + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                **params,
            )
            return resp.choices[0].message.content
        except (RateLimitError, APIError) as err:
            wait = 1.5 * attempt
            logging.warning(
                "OpenAI error: %s (retry %d/%d, sleep %.1fs)",
                err,
                attempt,
                retry_max,
                wait,
            )
            time.sleep(wait)
    raise RuntimeError("OpenAI failed after retries")


def extract_json_object(raw: str) -> Optional[dict[str, Any]]:
    """
    Pulls first balanced `{…}` object out of a string (Markdown-safe).
    Returns None on failure or if schema is unexpected.
    """
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    depth = None
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth is None:
                depth = 0
                start = i
            depth += 1
        elif ch == "}":
            if depth is not None:
                depth -= 1
                if depth == 0 and start is not None:
                    snippet = text[start : i + 1]
                    try:
                        parsed = json.loads(snippet)
                        required = {
                            "common_checklist",
                            "common_score",
                            "common_score_comment",
                            "local_checklist",
                            "local_score",
                            "local_score_comment",
                            "total_score",
                            "total_score_comment",
                            "grade",
                            "grade_explanation",
                            "comment",
                        }
                        if not required.issubset(parsed.keys()):
                            logging.error(
                                "Unexpected JSON schema: missing fields %s",
                                required - parsed.keys(),
                            )
                            return None
                        return parsed
                    except json.JSONDecodeError as e:
                        logging.warning(
                            "json.parse_failed: %s\nsnippet: %s",
                            e,
                            snippet[:60],
                        )
                        return None
    return None


def extract_grade_expl(answer: str) -> tuple[str, str]:
    """
    Extract "grade" and "grade_explanation" from the model's response.
    If JSON found, use fields; otherwise, fallback to regex parsing of "Grade: X – explanation".
    """
    parsed = extract_json_object(answer)
    if parsed is not None:
        grade = parsed.get("grade", "?")
        expl = parsed.get("grade_explanation", "") or parsed.get("explanation", "")
        return grade, expl.strip().replace("\n", " ")
    regex = re.compile(r"Grade:\s*([A-D])\s*[-–]\s*(.+)", re.IGNORECASE | re.DOTALL)
    m = regex.search(answer)
    if m:
        grade = m.group(1).upper()
        expl = m.group(2).strip()
        return grade, expl
    return "?", answer.strip().replace("\n", " ")


def sanitize_filename(name: str) -> str:
    """
    Replace spaces with underscores and remove characters that cannot appear in filenames.
    """
    return re.sub(r"[^\w\-]", "_", name.replace(" ", "_"))


def render_candidate_md(entry: Dict[str, Any]) -> str:
    """
    Create a per-candidate Markdown file with detailed, human-readable analysis.
    """
    data = entry.get("parsed_response", {})
    candidate = entry["candidate"]
    grade = data.get("grade", entry.get("grade", "?"))
    total_score = data.get("total_score", entry.get("score", 0))

    lines: List[str] = []
    lines.append(f"**Grade:** {grade} (total_score: {total_score})  \n")
    lines.append(f"## {candidate}\n")
    lines.append(f"**Company-fit = {data.get('common_score', 0)}**  ")
    lines.append(f"“{data.get('common_score_comment', '')}”\n")
    lines.append(f"**Vacancy-fit = {data.get('local_score', 0)}**  ")
    lines.append(f"“{data.get('local_score_comment', '')}”\n")
    lines.append(f"**Grade Explanation**  ")
    lines.append(f"“{data.get('grade_explanation', '')}”\n\n")

    lines.append(f"**Pros**  ")
    pros = data.get("comment", {}).get("pros", [])
    if pros:
        for p in pros:
            lines.append(f"- {p}  ")
    else:
        lines.append("- (нет)  ")

    lines.append(f"\n**Cons**  ")
    cons = data.get("comment", {}).get("cons", [])
    if cons:
        for c in cons:
            lines.append(f"- {c}  ")
    else:
        lines.append("- (нет)  ")

    return "\n".join(lines)


def render_md_summary(rows: List[Dict[str, Any]], candidate_md_dir: str = ".") -> str:
    """
    Markdown table with clickable links to per-candidate files (relative to summary's location).
    """
    lines = [
        "| Candidate | Grade | Explanation |",
        "|-----------|-------|-------------|",
    ]
    for r in rows:
        candidate = r["candidate"]
        grade = r["parsed_response"].get("grade", "?") if r.get("parsed_response") else r["grade"]
        data = r.get("parsed_response", {})
        grade_expl = data.get("grade_explanation", "")
        pros = data.get("comment", {}).get("pros", [])
        cons = data.get("comment", {}).get("cons", [])

        expl_lines: List[str] = []
        expl_lines.append(f"**Grade Explanation**<br>“{grade_expl}”")
        expl_lines.append(f"<br>**Pros**")
        if pros:
            for p in pros:
                expl_lines.append(f"<br>- {p}")
        else:
            expl_lines.append(f"<br>- (нет)")
        expl_lines.append(f"<br>**Cons**")
        if cons:
            for c in cons:
                expl_lines.append(f"<br>- {c}")
        else:
            expl_lines.append(f"<br>- (нет)")

        explanation_cell = "".join(expl_lines)
        filename = sanitize_filename(candidate) + ".md"
        candidate_link = f"[{candidate}]({candidate_md_dir}/{filename})"
        lines.append(f"| {candidate_link} | {grade} | {explanation_cell} |")

    return "\n".join(lines)


# ───────────────────────── main ─────────────────────────────

def main() -> None:
    setup_logging()
    cfg = load_config(BASE_DIR / "config.yaml")
    load_env()

    # 1) Создаём все каталоги, упомянутые в конфиге
    for key in ("out_json", "out_md_summary", "out_md_full", "candidate_md_dir"):
        abs_path(cfg["paths"][key]).parent.mkdir(parents=True, exist_ok=True)
    candidate_md_dir = abs_path(cfg["paths"]["candidate_md_dir"])
    candidate_md_dir.mkdir(parents=True, exist_ok=True)      # ←  ❗ обязательно

    client = OpenAI()

    sys_prompt = load_system_prompt(abs_path(cfg["paths"]["system_prompt"]))
    files = sorted(glob(str(abs_path(cfg["paths"]["candidates_glob"]))))

    results: List[Dict[str, Any]] = []
    for path in files:
        cand_doc = read_text(path)
        cid = candidate_id(cand_doc, Path(path).stem)

        messages = build_message(sys_prompt, cand_doc)
        answer = safe_chat(
            client=client,
            messages=messages,
            model=cfg["llm"]["model"],
            retry_max=cfg["llm"]["retry_max"],
            **cfg["llm"]["params"],
        )

        parsed = extract_json_object(answer)
        grade, expl = extract_grade_expl(answer)
        score = cfg["grading"]["scale"].get(grade, 0)

        entry: Dict[str, Any] = {
            "candidate": cid,
            "grade": grade,
            "score": score,
            "explanation": expl,
            "raw_response": answer,
        }
        if parsed:
            entry["parsed_response"] = parsed

        results.append(entry)
        logging.info("✓ %s → %s", cid, grade)

    sorted_results = sorted(results, key=lambda r: -r["score"])

    # Write results.json into data/output
    full_json = json.dumps(sorted_results, indent=2, ensure_ascii=False)
    abs_path(cfg["paths"]["out_json"]).write_text(full_json, encoding="utf-8")

    # Write per-candidate MD files into data/output/candidates_md
    for r in sorted_results:
        candidate = r["candidate"]
        filename = candidate_md_dir / (sanitize_filename(candidate) + ".md")
        content = render_candidate_md(r)
        Path(filename).write_text(content, encoding="utf-8")

    # Write summary table into data/output/results_summary.md
    # Относительная ссылка = «подкаталог рядом с summary»
    rel_link = Path(cfg["paths"]["candidate_md_dir"]).name   # "candidates_md"
    summary_md = render_md_summary(sorted_results, candidate_md_dir=rel_link)
    abs_path(cfg["paths"]["out_md_summary"]).write_text(summary_md, encoding="utf-8")


    logging.info("Finished: %d candidates", len(results))


if __name__ == "__main__":
    main()

# 012 - llm_resume_grader/requirements.txt
# llm_resume_grader/requirements.txt
openai==1.12.0
pyyaml
python-dotenv
pytest


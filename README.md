
# LLM Resume Grader (A–D, Aviasales-style)

Автоматизация скрининга резюме и сопроводительных писем с помощью OpenAI API и кастомных чеклистов — для честного, масштабируемого и объяснимого первичного отбора кандидатов на ИТ-вакансии.

## 🟢 Как это работает — в двух словах

1. **Запусти** `python3 main.py`
2. **Скрипт автоматически найдёт все резюме** в папке `candidates/`
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

# 5. Положи резюме-кандидатов в папку candidates/
# форматы смотри ниже

# 6. Запусти пайплайн
python3 main.py

# 7. Результаты будут в results.md и results.json
```

---

## 🗂 Структура репозитория

```
llm_resume_grader/
├── candidates/            # папка для резюме (.md)
│   ├── C001.md
│   └── C016.md
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



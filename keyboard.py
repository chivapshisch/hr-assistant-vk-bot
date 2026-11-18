import json

keyboard_main = json.dumps(
    {
        "one_time": True,
        "inline": False,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "vhod_user"}),
                        "label": "Пользователь",
                    },
                    "color": "primary",
                },
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "vhod_hr"}),
                        "label": "HR-менеджер",
                    },
                    "color": "secondary",
                },
            ]
        ],
    },
    ensure_ascii=False,
)

keyboard_hr = json.dumps(
    {
        "one_time": True,
        "inline": False,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "new_vakansia"}),
                        "label": "Добавить вакансию",
                    },
                    "color": "positive",
                },
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "see_otkliki"}),
                        "label": "Посмотреть отклики",
                    },
                    "color": "primary",
                },
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "poluchit_analitiku"}),
                        "label": "Получить аналитику",
                    },
                    "color": "secondary",
                },
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "delet_vakansia"}),
                        "label": "Удалить вакансию",
                    },
                    "color": "negative",
                },
            ],
        ],
    },
    ensure_ascii=False,
)

analit = json.dumps(
    {
        "one_time": True,
        "inline": False,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "poluchit_kluch"}),
                        "label": "Получить ключ",
                    },
                    "color": "primary",
                },
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "new_vakansia"}),
                        "label": "Добавить вакансию",
                    },
                    "color": "positive",
                },
            ],
            [
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "change_vakansia"}),
                        "label": "Изменить вакансию",
                    },
                    "color": "secondary",
                },
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "delet_vakansia"}),
                        "label": "Удалить вакансию",
                    },
                    "color": "negative",
                },
            ],
        ],
    },
    ensure_ascii=False,
)

yes_or_no = json.dumps(
    {
        "one_time": True,
        "inline": False,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "del_vakansia"}),
                        "label": "Удалить",
                    },
                    "color": "negative",
                },
                {
                    "action": {
                        "type": "text",
                        "payload": json.dumps({"command": "otmena_delet_vakansia"}),
                        "label": "Отмена",
                    },
                    "color": "secondary",
                },
            ]
        ],
    },
    ensure_ascii=False,
)

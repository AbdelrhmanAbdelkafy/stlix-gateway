"""The laws this advisor is supposed to have — and therefore the list of what
it is missing.

Read the second half of that sentence first. A legal assistant with an empty
corpus that simply says «مالقيتش حاجة» is useless; one that says *«السؤال ده
محكوم بقانون العمل، وأنا مش شايف نصّه — حمّله وأنا أجاوب بالمادة»* is useful
on its first day, before a single statute is loaded.

**What is deliberately not here: law numbers and years.** Every entry names a
law and says what it governs — both safe to state — and stops. `القانون رقم كذا
لسنة كذا` gets recorded only when the text is loaded and the number is read out
of the file. Typing those numbers here from memory would be the exact act this
platform spent a session deleting from the finance pages, committed in the one
domain where being wrong is most expensive: a contract citing the wrong article
is worse drafting than a contract citing none.

The list is scoped to what this company actually does — steel trading and
manufacturing in Cairo, importing from Foshan, employing ~206 people — not to
Egyptian law in general.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Expected:
    slug: str            # filename stem the loader looks for
    name: str            # as a lawyer would name it, without the number
    jurisdiction: str    # مصر · الصين · دولي
    covers: str          # why this company needs it
    tier: str = "statute"


EXPECTED: tuple[Expected, ...] = (
    # --- مصر: الإطار ---------------------------------------------------------
    Expected("dostor", "الدستور المصري", "مصر",
             "الحقوق والحريات · حدود التشريع · ما لا يجوز لأي عقد أن يخالفه"),
    Expected("madani", "القانون المدني", "مصر",
             "أصل كل عقد: التراضي · المحل · السبب · البطلان · الفسخ · التعويض · "
             "التقادم · الإيجار · البيع · المقاولة"),
    Expected("tegari", "قانون التجارة", "مصر",
             "الأعمال التجارية · التاجر · الدفاتر · البيوع التجارية · الوكالة "
             "التجارية · الأوراق التجارية · الإفلاس"),
    Expected("sharikat", "قانون الشركات", "مصر",
             "التأسيس · رأس المال · مجلس الإدارة · الجمعية العامة · تعديل عقد "
             "التأسيس — الكيانات الثلاثة بتاعتنا"),

    # --- مصر: الناس ----------------------------------------------------------
    Expected("amal", "قانون العمل", "مصر",
             "عقد العمل · الأجر · ساعات العمل · الإجازات · الجزاءات · إنهاء "
             "الخدمة · التعويض — الـ206 موظف"),
    Expected("khedma-madaniya", "قانون الخدمة المدنية", "مصر",
             "العاملون المدنيون بالدولة — مرجع مقارن للوائحنا الداخلية، "
             "ومُلزم في أي تعامل مع جهة حكومية"),
    Expected("taminat", "قانون التأمينات الاجتماعية", "مصر",
             "الاشتراكات · الأجر التأميني · إصابات العمل · المعاش"),

    # --- مصر: الجنائي --------------------------------------------------------
    Expected("oqubat", "قانون العقوبات", "مصر",
             "خيانة الأمانة · النصب · التزوير · الاختلاس — الجرائم اللي بتقع في "
             "بيئة شركة فعلًا"),
    Expected("egraat-genaeya", "قانون الإجراءات الجنائية", "مصر",
             "المحضر · التحقيق · الدعوى المدنية بالتبعية — إيه اللي بيحصل لما "
             "نبلّغ"),

    # --- مصر: الشغل نفسه -----------------------------------------------------
    Expected("gamarek", "قانون الجمارك", "مصر",
             "الإفراج · القيمة الجمركية · التظلم — كل شحنة داخلة من فوشان"),
    Expected("dakhl", "قانون الضريبة على الدخل", "مصر",
             "الوعاء · الخصم تحت حساب الضريبة · التكاليف واجبة الخصم"),
    Expected("qema-modafa", "قانون ضريبة القيمة المضافة", "مصر",
             "التسجيل · الخصم · الفاتورة الإلكترونية"),
    Expected("estithmar", "قانون الاستثمار", "مصر",
             "الحوافز · الضمانات · تسوية المنازعات الاستثمارية"),
    Expected("tawqee-electroni", "قانون التوقيع الإلكتروني", "مصر",
             "حجّية التوقيع الإلكتروني — الأساس القانوني لآلية التوقيع في المنصّة (PA5)"),
    Expected("hemayat-bayanat", "قانون حماية البيانات الشخصية", "مصر",
             "بيانات الموظفين والعملاء · الموافقة · النقل خارج البلد"),
    Expected("monafasa", "قانون حماية المنافسة ومنع الممارسات الاحتكارية", "مصر",
             "الاتفاقات المحظورة · إساءة استغلال الوضع المسيطر"),

    # --- الصين: الطرف التاني في كل عقد استيراد -------------------------------
    Expected("cn-civil-code", "القانون المدني الصيني", "الصين",
             "قانون العقود الصيني اندمج فيه — القانون الحاكم لو المورّد فرض قانونه"),
    Expected("cn-company-law", "قانون الشركات الصيني", "الصين",
             "التحقّق من أهلية المورّد ومَن يملك حق التوقيع عنه"),
    Expected("cn-foreign-trade", "قانون التجارة الخارجية الصيني", "الصين",
             "التصدير · التراخيص · القيود"),

    # --- دولي ----------------------------------------------------------------
    Expected("cisg", "اتفاقية الأمم المتحدة للبيع الدولي للبضائع (CISG)", "دولي",
             "بتطبّق تلقائيًا على البيع بين طرفين في دولتين طرفين ما لم تُستبعد "
             "صراحةً — أهم نص في عقود الاستيراد بتاعتنا"),
    Expected("new-york-convention", "اتفاقية نيويورك للاعتراف بأحكام التحكيم "
             "الأجنبية وتنفيذها", "دولي",
             "هل حكم التحكيم اللي هنكسبه ينفَّذ في الصين فعلًا"),
    Expected("incoterms", "قواعد الإنكوترمز (غرفة التجارة الدولية)", "دولي",
             "FOB · CIF · EXW — انتقال المخاطر والمصاريف. قواعد تعاقدية، مش قانون",
             tier="statute"),

    # --- بتاعنا إحنا ---------------------------------------------------------
    Expected("lawaeh-dakhiliya", "اللوائح الداخلية للمجموعة", "ستليكس",
             "لائحة الجزاءات · المشتريات · الموارد البشرية — 18 لائحة، صفر "
             "مصدّقة من المديرية (من حزمة REP)", tier="internal"),
    Expected("oqoud-mowaqqaa", "العقود الموقّعة", "ستليكس",
             "الإيجارات · التأسيس · عقود العمل · عقد فوشان — سوابقنا إحنا: "
             "إزاي كتبنا البند ده قبل كده", tier="precedent"),
)

BY_SLUG = {e.slug: e for e in EXPECTED}

-- ============================================================
-- استعلامات الأرصدة الحيّة — الصقها في نما: /erp/vue.html#/utils/sql
-- (أداة SQL في نما بتشتغل بصلاحية دخولك — قراءة فقط، آمنة)
-- ============================================================

-- 1) أرصدة العملاء (مرتّبة بالأكثر استحقاقًا)
SELECT  c.code                       AS الكود,
        c.name1                      AS العميل,
        COUNT(*)                     AS عدد_الفواتير,
        SUM(s.total)                 AS اجمالي_المبيعات,
        SUM(s.totalPaid)             AS المحصّل,
        SUM(s.remaining)             AS المستحق,
        MAX(s.issueDate)             AS اخر_فاتورة
FROM    SalesInvoice s
JOIN    Customer c ON c.id = s.customer_id
GROUP BY c.code, c.name1
ORDER BY SUM(s.remaining) DESC;

-- 2) أرصدة الموردين (المستحق علينا)
SELECT  sup.code                     AS الكود,
        sup.name1                    AS المورد,
        COUNT(*)                     AS عدد_الفواتير,
        SUM(p.total)                 AS اجمالي_المشتريات,
        SUM(p.totalPaid)             AS المدفوع,
        SUM(p.remaining)             AS المستحق,
        MAX(p.issueDate)             AS اخر_فاتورة
FROM    PurchaseInvoice p
JOIN    Supplier sup ON sup.id = p.supplier_id
GROUP BY sup.code, sup.name1
ORDER BY SUM(p.remaining) DESC;

-- 3) الإجماليات التنفيذية للشركة (KPIs)
SELECT
  (SELECT COUNT(*) FROM Customer)               AS عدد_العملاء,
  (SELECT COUNT(*) FROM Supplier)               AS عدد_الموردين,
  (SELECT SUM(total)     FROM SalesInvoice)     AS اجمالي_المبيعات,
  (SELECT SUM(remaining) FROM SalesInvoice)     AS مستحق_لنا_AR,
  (SELECT SUM(total)     FROM PurchaseInvoice)  AS اجمالي_المشتريات,
  (SELECT SUM(remaining) FROM PurchaseInvoice)  AS مستحق_علينا_AP;

-- 4) كشف حساب عميل معيّن — غيّر الكود C1000001
SELECT  s.code AS الفاتورة, s.issueDate AS التاريخ,
        s.total AS الاجمالي, s.totalPaid AS المدفوع, s.remaining AS المتبقي
FROM    SalesInvoice s
JOIN    Customer c ON c.id = s.customer_id
WHERE   c.code = 'C1000001'
ORDER BY s.issueDate DESC;

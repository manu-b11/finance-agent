import { formatCOP } from '../../lib/format.js'

/*
  data = resultado de la tool get_expenses_by_category
  { total_expenses, categories: [{ category, label, total, percentage }], top_category }
*/
export default function CategoriesCard({ data }) {
  const categories = data?.categories ?? []
  const total = data?.total_expenses

  return (
    <div className="card statement-card">
      <div className="card-head">
        <b>Gastos por categoría</b>
        <span className="badge">{formatCOP(total)}</span>
      </div>
      <div className="card-body">
        {categories.length === 0 ? (
          <div className="row"><span>No hay gastos en ese periodo.</span></div>
        ) : (
          categories.map((item) => (
            <div className="cat-row" key={item.category}>
              <div className="cat-line">
                <span>{item.label}</span>
                <span>{formatCOP(item.total)}</span>
              </div>
              <div className="cat-bar">
                <i
                  style={{
                    width: `${Math.max(2, Math.min(100, Number(item.percentage)))}%`,
                  }}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

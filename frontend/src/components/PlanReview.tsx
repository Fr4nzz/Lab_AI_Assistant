import { PlanStep, Suggestion } from '../api/client'

interface Props {
  plan: {
    understanding: string
    steps: PlanStep[]
    suggestions: Suggestion[]
  }
  onApprove: () => void
  onCancel: () => void
  isLoading: boolean
}

export default function PlanReview({ plan, onApprove, onCancel, isLoading }: Props) {
  return (
    <div className="plan-review">
      <h3>📝 Plan de Ejecución</h3>
      
      <div className="plan-steps">
        <h4>Pasos a ejecutar:</h4>
        <ol>
          {plan.steps.map((step, i) => (
            <li key={i}>
              <span className="step-action">{step.action}</span>
              {step.description && (
                <span className="step-description"> - {step.description}</span>
              )}
            </li>
          ))}
        </ol>
      </div>

      {plan.suggestions.length > 0 && (
        <div className="plan-suggestions">
          <h4>💡 Sugerencias:</h4>
          {plan.suggestions.map((sug, i) => (
            <div key={i} className="suggestion">
              <label>
                <input type="checkbox" defaultChecked={sug.apply} />
                {sug.message}
              </label>
            </div>
          ))}
        </div>
      )}

      <div className="plan-actions">
        <button 
          className="approve-btn"
          onClick={onApprove}
          disabled={isLoading}
        >
          ✓ Ejecutar Plan
        </button>
        <button 
          className="cancel-btn"
          onClick={onCancel}
          disabled={isLoading}
        >
          ✕ Cancelar
        </button>
      </div>

      <p className="plan-warning">
        ⚠️ Nota: El agente llenará los campos pero <strong>NO</strong> hará click en "Guardar". 
        Deberás hacerlo manualmente después de verificar.
      </p>
    </div>
  )
}

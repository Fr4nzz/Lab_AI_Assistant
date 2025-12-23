import { ExtractedData } from '../api/client'

interface Props {
  data: ExtractedData[]
  onChange: (data: ExtractedData[]) => void
}

export default function DataTable({ data, onChange }: Props) {
  const updateField = (
    patientIndex: number, 
    fieldIndex: number, 
    key: 'field' | 'value' | 'unit', 
    newValue: string
  ) => {
    const newData = [...data]
    newData[patientIndex] = {
      ...newData[patientIndex],
      fields: newData[patientIndex].fields.map((f, i) => 
        i === fieldIndex ? { ...f, [key]: newValue } : f
      )
    }
    onChange(newData)
  }

  const updatePatientInfo = (
    index: number,
    key: 'patient' | 'exam',
    value: string
  ) => {
    const newData = [...data]
    newData[index] = { ...newData[index], [key]: value }
    onChange(newData)
  }

  const removeField = (patientIndex: number, fieldIndex: number) => {
    const newData = [...data]
    newData[patientIndex] = {
      ...newData[patientIndex],
      fields: newData[patientIndex].fields.filter((_, i) => i !== fieldIndex)
    }
    onChange(newData)
  }

  const addField = (patientIndex: number) => {
    const newData = [...data]
    newData[patientIndex] = {
      ...newData[patientIndex],
      fields: [...newData[patientIndex].fields, { field: '', value: '', unit: '' }]
    }
    onChange(newData)
  }

  return (
    <div className="data-table-container">
      <h3>📋 Datos Extraídos (editables)</h3>
      
      {data.map((item, pIdx) => (
        <div key={pIdx} className="patient-section">
          <div className="patient-header">
            <input
              type="text"
              value={item.patient}
              onChange={e => updatePatientInfo(pIdx, 'patient', e.target.value)}
              placeholder="Nombre del paciente"
              className="patient-input"
            />
            <input
              type="text"
              value={item.exam}
              onChange={e => updatePatientInfo(pIdx, 'exam', e.target.value)}
              placeholder="Examen"
              className="exam-input"
            />
          </div>
          
          <table className="fields-table">
            <thead>
              <tr>
                <th>Campo</th>
                <th>Valor</th>
                <th>Unidad</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {item.fields.map((field, fIdx) => (
                <tr key={fIdx}>
                  <td>
                    <input
                      type="text"
                      value={field.field}
                      onChange={e => updateField(pIdx, fIdx, 'field', e.target.value)}
                      placeholder="Campo"
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={field.value}
                      onChange={e => updateField(pIdx, fIdx, 'value', e.target.value)}
                      placeholder="Valor"
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={field.unit || ''}
                      onChange={e => updateField(pIdx, fIdx, 'unit', e.target.value)}
                      placeholder="Unidad"
                    />
                  </td>
                  <td>
                    <button 
                      className="remove-btn"
                      onClick={() => removeField(pIdx, fIdx)}
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          <button 
            className="add-field-btn"
            onClick={() => addField(pIdx)}
          >
            + Agregar campo
          </button>
        </div>
      ))}
    </div>
  )
}

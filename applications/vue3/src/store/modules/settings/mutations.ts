import {
  FETCH_COMPANY,
  FETCH_COMPANY_LIST,
} from '@/store/modules/settings/mutations-types'
import { Company, CompanyState } from '@/store/modules/settings/state'

const mutations = {
  [FETCH_COMPANY_LIST]: (state: CompanyState, payload: Company[]) => {
    state.companyList = payload
  },

  [FETCH_COMPANY]: (state: CompanyState, payload: Company) => {
    state.company = payload
  },
}

export default mutations

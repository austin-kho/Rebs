import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import FileUpload from '../FileUpload.vue'

describe('FileUpload Component Test', () => {
  it('should ', () => {
    const wrapper = mount(FileUpload)

    expect(wrapper.find('input[type=file]').exists()).toBeTruthy()
  })
})

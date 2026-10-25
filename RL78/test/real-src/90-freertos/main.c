/* Ghidra-Rare RL78 test program: FreeRTOS (MIT) kernel with two tasks and a queue. */
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"

static QueueHandle_t q;
static SemaphoreHandle_t m;
volatile unsigned long received;

static void producer(void *arg)
{
	unsigned short n = 0;
	(void)arg;
	for (;;) {
		xQueueSend(q, &n, portMAX_DELAY);
		n++;
		vTaskDelay(10);
	}
}

static void consumer(void *arg)
{
	unsigned short v;
	(void)arg;
	for (;;) {
		if (xQueueReceive(q, &v, portMAX_DELAY) == pdPASS) {
			xSemaphoreTake(m, portMAX_DELAY);
			received += v;
			xSemaphoreGive(m);
		}
	}
}

int main(void)
{
	q = xQueueCreate(4, sizeof(unsigned short));
	m = xSemaphoreCreateMutex();
	xTaskCreate(producer, "prod", configMINIMAL_STACK_SIZE, NULL, 1, NULL);
	xTaskCreate(consumer, "cons", configMINIMAL_STACK_SIZE, NULL, 2, NULL);
	vTaskStartScheduler();
	for (;;)
		;
}
